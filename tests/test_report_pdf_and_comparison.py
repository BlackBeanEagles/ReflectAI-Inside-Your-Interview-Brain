"""
API-level tests for the PDF report download endpoint and the
compare-to-own-history feature wired into POST /session/{id}/report.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    # Clear the rate limiter's shared in-process bucket before each test —
    # TestClient requests all share one fake client IP, so accumulated
    # requests from earlier test files in the same pytest run could
    # otherwise trip the real 20-req/60s limit here and fail on an
    # unrelated 429 rather than the thing this test actually checks.
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


def _add_answer(client, sid, score=6.0):
    body = {
        "session_id": sid,
        "question": "What is REST?",
        "answer": "REST is an HTTP-based style for APIs.",
        "round_type": "technical",
        "scores": {"correctness": score, "clarity": score, "depth": score, "completeness": score},
        "final_score": score,
        "feedback": {"strength": "Clear.", "weakness": "Thin.", "improvement": "Add an example."},
    }
    r = client.post("/session/add-interaction", json=body)
    assert r.status_code == 200


def test_report_pdf_endpoint_returns_a_pdf(client):
    r0 = client.post("/session/start")
    sid = r0.json()["session_id"]
    _add_answer(client, sid)

    r = client.get(f"/session/{sid}/report/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers["content-disposition"]


def test_report_pdf_endpoint_works_for_empty_session(client):
    r0 = client.post("/session/start")
    sid = r0.json()["session_id"]
    r = client.get(f"/session/{sid}/report/pdf")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_report_pdf_endpoint_works_for_unknown_session(client):
    """Empty history, same as a fresh session — must not 500."""
    r = client.get("/session/nonexistent-session-id/report/pdf")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_report_json_has_no_comparison_when_anonymous(client):
    r0 = client.post("/session/start")
    sid = r0.json()["session_id"]
    _add_answer(client, sid)
    r = client.post(f"/session/{sid}/report")
    assert r.status_code == 200
    assert r.json()["comparison"] is None


def test_report_json_has_comparison_for_logged_in_user_with_history(client, monkeypatch):
    from services import db

    store_reports = []

    def fake_is_enabled():
        return True

    def fake_get_user_reports(user_id, limit=20):
        return store_reports

    def fake_save_report(session_id, report, user_id=None):
        store_reports.append({"session_id": session_id, "report": dict(report), "created_at": "2026-01-01T00:00:00"})

    monkeypatch.setattr(db, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(db, "get_user_reports", fake_get_user_reports)
    monkeypatch.setattr(db, "save_report", fake_save_report)

    from api.routes.auth import get_optional_user
    app.dependency_overrides[get_optional_user] = lambda: {"user_id": 1, "email": "a@b.com"}
    try:
        # First session: no prior history yet.
        r0 = client.post("/session/start", json={"store_consent": True})
        sid1 = r0.json()["session_id"]
        _add_answer(client, sid1, score=5.0)
        r1 = client.post(f"/session/{sid1}/report")
        assert r1.json()["comparison"] is None  # nothing to compare against yet

        # Second session: should now compare against the first (saved above).
        r0b = client.post("/session/start", json={"store_consent": True})
        sid2 = r0b.json()["session_id"]
        _add_answer(client, sid2, score=8.0)
        r2 = client.post(f"/session/{sid2}/report")
        comparison = r2.json()["comparison"]
        assert comparison is not None
        assert comparison["overall_score"]["session_count"] == 1
        assert comparison["overall_score"]["delta"] > 0  # 8.0 session scored higher than the 5.0 one
    finally:
        app.dependency_overrides.pop(get_optional_user, None)
