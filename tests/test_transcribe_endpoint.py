"""API-level tests for POST /transcribe-audio, including the voice_analysis
block it now attaches via services/voice_analysis.py."""

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


def _fake_wav_bytes() -> bytes:
    return b"RIFF....WAVEfmt fake audio content for testing"


def test_transcribe_endpoint_returns_voice_analysis_on_success(client, monkeypatch):
    import services.speech as speech

    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "text": "Um, so the answer is basically about caching.",
                "duration": 5.0,
                "words": [
                    {"word": w, "start": i * 0.5, "end": i * 0.5 + 0.3}
                    for i, w in enumerate(
                        "Um, so the answer is basically about caching.".split()
                    )
                ],
            }

    monkeypatch.setattr(speech.requests, "post", lambda *a, **kw: FakeResponse())

    r = client.post(
        "/transcribe-audio",
        files={"file": ("answer.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_error"] is False
    assert "caching" in body["text"].lower()
    assert body["voice_analysis"] is not None
    assert "filler_words" in body["voice_analysis"]
    assert "confidence" in body["voice_analysis"]
    assert body["voice_analysis"]["pace"] is not None  # duration was provided


def test_transcribe_endpoint_omits_voice_analysis_on_transcription_error(client, monkeypatch):
    import services.speech as speech
    monkeypatch.setattr(speech, "GROQ_API_KEY", "")  # forces the no-key error path

    r = client.post(
        "/transcribe-audio",
        files={"file": ("answer.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_error"] is True
    assert body["voice_analysis"] is None


def test_transcribe_endpoint_survives_voice_analysis_failure(client, monkeypatch):
    """If analyze_voice_answer blows up for some reason, the transcript must
    still come back -- analysis is a bonus, not a dependency."""
    import services.speech as speech
    import api.routes.evaluation as evaluation_route

    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"text": "A normal transcript."}

    monkeypatch.setattr(speech.requests, "post", lambda *a, **kw: FakeResponse())

    def broken_analyze(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(evaluation_route, "analyze_voice_answer", broken_analyze)

    r = client.post(
        "/transcribe-audio",
        files={"file": ("answer.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_error"] is False
    assert body["text"] == "A normal transcript."
    assert body["voice_analysis"] is None
