"""API-level tests for POST /ats-score -- particularly that job_description
is genuinely optional now (see services/ats_scorer.py for the scoring-side
behavior when it's absent)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    # /ats-score is rate-limited (app/main.py) -- TestClient requests all
    # share one fake client IP, so accumulated requests from earlier test
    # files in the same pytest run could otherwise trip the real 20-req/60s
    # limit here and fail on an unrelated 429.
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


RESUME_TEXT = "Skills: Python, Django\nExperience:\n- Built REST APIs.\nEmail: a@b.com"


def test_ats_score_without_job_description_returns_200(client):
    r = client.post("/ats-score", data={"text": RESUME_TEXT})
    assert r.status_code == 200
    body = r.json()
    assert body["has_job_description"] is False
    assert all(c["key"] != "keyword_match" for c in body["categories"])
    assert sum(c["weight"] for c in body["categories"]) == 100


def test_ats_score_with_job_description_returns_200(client):
    r = client.post(
        "/ats-score",
        data={"text": RESUME_TEXT, "job_description": "Looking for a Python/Django developer."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_job_description"] is True
    assert any(c["key"] == "keyword_match" for c in body["categories"])


def test_ats_score_still_requires_a_resume(client):
    r = client.post("/ats-score", data={"job_description": "Python developer wanted."})
    assert r.status_code == 400


def test_ats_score_rejects_oversized_job_description(client):
    r = client.post("/ats-score", data={"text": RESUME_TEXT, "job_description": "x" * 20000})
    assert r.status_code == 413
