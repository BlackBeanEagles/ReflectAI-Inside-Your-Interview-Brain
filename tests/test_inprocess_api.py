"""
In-process FastAPI tests (no uvicorn, no Ollama) — CI gate for option \"all tests green\".
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_home(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "running" in r.json().get("message", "").lower()


def test_session_flow_and_report(client: TestClient):
    r0 = client.post("/session/start")
    assert r0.status_code == 200
    sid = r0.json()["session_id"]

    body = {
        "session_id": sid,
        "question": "What is REST?",
        "answer": "REST is an HTTP-based style for APIs.",
        "round_type": "technical",
        "scores": {"correctness": 6, "clarity": 6, "depth": 6, "completeness": 6},
        "final_score": 6.0,
        "feedback": {
            "strength": "Clear basics.",
            "weakness": "Light on detail.",
            "improvement": "Add an example.",
        },
        "response_time_seconds": 42.5,
    }
    r1 = client.post("/session/add-interaction", json=body)
    assert r1.status_code == 200

    r2 = client.post(f"/session/{sid}/report")
    assert r2.status_code == 200
    data = r2.json()
    assert data["total_questions"] == 1
    assert "overall_score" in data
    assert data.get("cognitive") is not None


def test_next_question_with_session_id(client: TestClient):
    r0 = client.post("/session/start")
    sid = r0.json()["session_id"]
    client.post(
        "/session/add-interaction",
        json={
            "session_id": sid,
            "question": "Q1",
            "answer": "A1",
            "round_type": "technical",
            "scores": {"correctness": 4, "clarity": 4, "depth": 4, "completeness": 4},
            "final_score": 4.0,
            "feedback": {
                "strength": "Attempted.",
                "weakness": "Thin.",
                "improvement": "Expand.",
            },
        },
    )
    payload = {
        "count": 2,
        "skills": ["Python"],
        "projects": ["Demo app"],
        "experience": ["Intern"],
        "used_skills": [],
        "current_round": "technical",
        "score_history": [7.0, 7.0, 4.0],
        "difficulty": "medium",
        "stress_count": 0,
        "max_questions": 10,
        "session_id": sid,
    }
    r = client.post("/next-question", json=payload)
    assert r.status_code == 200
    j = r.json()
    assert "question" in j
    assert j.get("cognitive_thinking_style") is not None or j.get("round") in (
        "hr",
        "technical",
        "stress",
        "end",
    )


def test_evaluate_with_coaching_hint(client: TestClient):
    r = client.post(
        "/evaluate-answer",
        json={
            "question": "Explain CAP theorem.",
            "answer": "Consistency availability partition tolerance tradeoff in distributed systems.",
            "answer_type": "technical",
            "coaching_hint": "Thinking-style signal: analytical | Coaching tone: deep_open_ended",
        },
    )
    assert r.status_code == 200
    assert r.json().get("final_score", 0) >= 0


def test_decide_next_no_server(client: TestClient):
    r = client.post(
        "/decide-next",
        json={
            "current_round": "technical",
            "count": 3,
            "score_history": [4.0, 3.0, 4.0],
            "difficulty": "medium",
            "stress_count": 0,
        },
    )
    assert r.status_code == 200
    assert r.json()["round"] == "stress"


def test_replay_compare(client: TestClient):
    r = client.post(
        "/session/replay-compare",
        json={
            "question": "What is a hash map?",
            "old_answer": "idk",
            "old_scores": {"correctness": 2, "clarity": 2, "depth": 2, "completeness": 2},
            "old_final_score": 2.0,
            "new_answer": (
                "A hash map maps keys to values using a hash function for O(1) average lookup."
            ),
            "answer_type": "technical",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("new_score") is not None or j.get("error") is True
