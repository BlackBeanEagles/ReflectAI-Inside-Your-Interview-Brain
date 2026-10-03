"""
The report carries its transcript.

Until this, a report was aggregates only, and nobody could reread what
they had actually said next to the feedback on it. The History page even
advertised a "question-by-question breakdown" that no saved report
contained. The transcript is now part of the report -- returned with it,
and saved with it so History can show it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import services.db as db
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _answer(client, sid, question, answer, score=6.0, round_type="technical"):
    r = client.post("/session/add-interaction", json={
        "session_id": sid,
        "question": question,
        "answer": answer,
        "round_type": round_type,
        "scores": {"structure": score, "relevance": score, "communication": score, "confidence": score},
        "final_score": score,
        "feedback": {
            "strength": "Clear timeline.",
            "weakness": "No numbers.",
            "improvement": "Quantify the impact.",
        },
    })
    assert r.status_code == 200, r.text


def _start(client, consent=False):
    r = client.post("/session/start", json={"store_consent": consent})
    return r.json()["session_id"]


def test_the_report_contains_every_answer_in_order(client):
    sid = _start(client)
    _answer(client, sid, "Tell me about an outage.", "Redis failed over at 2am.", 7.0, "hr")
    _answer(client, sid, "How did you size the pool?", "From p99 latency under load.", 5.5)

    transcript = client.post(f"/session/{sid}/report").json()["transcript"]

    assert [t["question"] for t in transcript] == ["Tell me about an outage.", "How did you size the pool?"]
    assert transcript[0]["answer"] == "Redis failed over at 2am."
    assert transcript[0]["round"] == "hr"
    assert transcript[0]["final_score"] == 7.0
    assert transcript[1]["feedback"]["improvement"] == "Quantify the impact."


def test_an_empty_session_has_an_empty_transcript(client):
    sid = _start(client)
    assert client.post(f"/session/{sid}/report").json()["transcript"] == []


def test_the_transcript_is_saved_with_the_report_under_consent(client):
    # History reads saved reports, so the transcript has to be in the dict
    # that gets saved, not only in the response.
    sid = _start(client, consent=True)
    _answer(client, sid, "Tell me about an outage.", "Redis failed over.")
    with patch.object(db, "save_report") as save:
        client.post(f"/session/{sid}/report")
    saved = save.call_args.args[1]
    assert saved["transcript"][0]["answer"] == "Redis failed over."


def test_nothing_is_saved_without_consent(client):
    # The transcript is the user's own answers, so it does not get a weaker
    # storage rule than the answers themselves.
    sid = _start(client, consent=False)
    _answer(client, sid, "Q?", "A.")
    with patch.object(db, "save_report") as save:
        client.post(f"/session/{sid}/report")
    save.assert_not_called()


def test_blank_feedback_lines_are_dropped():
    from api.routes.session import _build_transcript

    out = _build_transcript([{
        "question": "Q?", "answer": "A.", "round": "hr", "final_score": 5,
        "feedback": {"strength": "Good.", "weakness": "  ", "improvement": ""},
    }])
    assert out[0]["feedback"] == {"strength": "Good."}


def test_a_malformed_entry_is_skipped_rather_than_failing_the_report():
    from api.routes.session import _build_transcript

    out = _build_transcript([
        {"question": "", "answer": "orphan answer"},
        {"question": "Real?", "answer": "Yes.", "final_score": None},
    ])
    assert len(out) == 1
    assert out[0]["final_score"] == 0.0
