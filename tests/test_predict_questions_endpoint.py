"""API-level tests for POST /predict-questions."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


def _fake_predictions(*a, **kw):
    return {
        "questions": [
            {"category": "technical", "question": "How does your caching layer work?", "prep_tip": "Mention TTL."},
            {"category": "hr", "question": "Why this role?", "prep_tip": "Be specific."},
        ],
        "error": False,
        "message": "",
    }


def test_predict_questions_with_role_only(client, monkeypatch):
    import api.routes.resume as resume_route
    monkeypatch.setattr(resume_route, "predict_questions", _fake_predictions)

    r = client.post("/predict-questions", data={"role": "Backend Engineer"})
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is False
    assert len(body["questions"]) == 2
    assert body["questions"][0]["category"] == "technical"


def test_predict_questions_with_resume_text(client, monkeypatch):
    import api.routes.resume as resume_route
    monkeypatch.setattr(resume_route, "predict_questions", _fake_predictions)

    r = client.post("/predict-questions", data={"text": "Skills: Python, Django\nProjects: Chatbot"})
    assert r.status_code == 200
    assert r.json()["error"] is False


def test_predict_questions_job_description_too_long_rejected(client):
    r = client.post("/predict-questions", data={"job_description": "x" * 20000})
    assert r.status_code == 413


def test_predict_questions_propagates_service_error(client, monkeypatch):
    import api.routes.resume as resume_route

    def fake_error(*a, **kw):
        return {"questions": [], "error": True, "message": "Could not generate questions right now. Try again."}

    monkeypatch.setattr(resume_route, "predict_questions", fake_error)
    r = client.post("/predict-questions", data={"role": "Backend Engineer"})
    assert r.status_code == 200  # errors are surfaced in the body, not an HTTP failure
    body = r.json()
    assert body["error"] is True
    assert body["questions"] == []
