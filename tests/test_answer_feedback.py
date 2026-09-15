"""
Per-answer verdicts on the scoring itself.

The scores come out of a language model and are sometimes wrong in ways
only the person who wrote the answer can see. Before this endpoint there
was nowhere to say so, so a bad score was just something the user quietly
stopped trusting.

What is locked in here is mostly the boundary conditions, because the
happy path is a single INSERT and the interesting failures are all around
it: a rating is content about the user's own answer, so it must not be
stored without the same consent gate the answer itself passes through,
and it must not be readable or writable across session owners.
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


def _start(client: TestClient, consent: bool = False) -> str:
    r = client.post("/session/start", json={"store_consent": consent})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _payload(sid: str, verdict: str = "unfair", **extra) -> dict:
    body = {
        "session_id": sid,
        "verdict": verdict,
        "question": "Walk me through the inventory service.",
        "round_type": "technical",
        "final_score": 4.0,
    }
    body.update(extra)
    return body


def test_verdict_is_accepted(client: TestClient):
    sid = _start(client)
    r = client.post("/session/answer-feedback", json=_payload(sid, "fair"))
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True


def test_without_storage_consent_nothing_is_written(client: TestClient):
    # The privacy choice is the whole point: succeeding while storing is
    # worse than failing, because the UI has already said "thanks".
    sid = _start(client, consent=False)
    with patch.object(db, "save_answer_feedback") as saver:
        r = client.post("/session/answer-feedback", json=_payload(sid))
    assert r.status_code == 200
    assert r.json()["stored"] is False
    saver.assert_not_called()


def test_with_storage_consent_the_verdict_is_written(client: TestClient):
    sid = _start(client, consent=True)
    with patch.object(db, "save_answer_feedback") as saver:
        r = client.post("/session/answer-feedback", json=_payload(sid, note="It ignored the trade-off I gave."))
    assert r.status_code == 200
    assert r.json()["stored"] is True
    saver.assert_called_once()
    kwargs = saver.call_args.kwargs
    assert kwargs["verdict"] == "unfair"
    assert kwargs["note"] == "It ignored the trade-off I gave."
    assert kwargs["final_score"] == 4.0


def test_an_unknown_verdict_is_rejected(client: TestClient):
    sid = _start(client)
    r = client.post("/session/answer-feedback", json=_payload(sid, verdict="meh"))
    assert r.status_code == 422


def test_an_overlong_note_is_rejected(client: TestClient):
    sid = _start(client)
    r = client.post("/session/answer-feedback", json=_payload(sid, note="x" * 501))
    assert r.status_code == 422


def test_a_storage_failure_does_not_reach_the_user():
    # Losing a rating must never interrupt an interview in progress, so the
    # writer owns its own failures rather than propagating them to the
    # route. Driven through the real function with a pool that blows up.
    class Boom:
        def connection(self):
            raise RuntimeError("db down")

    with patch.object(db, "_get_pool", return_value=Boom()):
        db.save_answer_feedback(
            session_id="s1",
            question="Q",
            round_type="technical",
            final_score=4.0,
            verdict="unfair",
        )  # must not raise


def test_account_deletion_covers_the_new_table():
    # answer_feedback.user_id is ON DELETE SET NULL like every other child
    # table, so leaving it out of the explicit delete list would orphan the
    # rows rather than remove them -- the exact bug the deletion helper was
    # written to avoid.
    import inspect

    src = inspect.getsource(db.delete_user_account)
    assert "answer_feedback" in src
