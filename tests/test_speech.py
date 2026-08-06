"""Unit tests for services/speech.py — Groq Whisper transcription (mocked, no network)."""

import services.speech as speech


def test_unavailable_when_no_api_key(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "")
    result = speech.transcribe_audio(b"fake audio bytes")
    assert result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)
    assert not speech.is_available()


def test_is_available_true_when_key_set(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")
    assert speech.is_available()


def test_empty_audio_returns_error_without_network_call(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")
    result = speech.transcribe_audio(b"")
    assert result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)


def test_oversized_audio_rejected_without_network_call(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(speech, "MAX_AUDIO_BYTES", 10)
    result = speech.transcribe_audio(b"way more than ten bytes of fake audio")
    assert result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)
    assert "too large" in result.lower() or "large" in result.lower()


def test_successful_transcription(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        text = "This is my transcribed answer."
        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        assert "audio/transcriptions" in url
        assert headers["Authorization"] == "Bearer gsk_fake"
        assert data["model"] == speech.GROQ_WHISPER_MODEL
        return FakeResponse()

    monkeypatch.setattr(speech.requests, "post", fake_post)
    result = speech.transcribe_audio(b"real-looking audio bytes")
    assert result == "This is my transcribed answer."
    assert not result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)


def test_empty_transcript_is_treated_as_error(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        text = "   "
        def raise_for_status(self):
            pass

    monkeypatch.setattr(speech.requests, "post", lambda *a, **kw: FakeResponse())
    result = speech.transcribe_audio(b"silence")
    assert result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)
    assert "no speech" in result.lower()


def test_timeout_is_handled_gracefully(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    def fake_post(*a, **kw):
        import requests
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(speech.requests, "post", fake_post)
    result = speech.transcribe_audio(b"audio bytes")
    assert result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)
    assert "timed out" in result.lower()


def test_unexpected_exception_never_raises(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    def fake_post(*a, **kw):
        raise RuntimeError("network is on fire")

    monkeypatch.setattr(speech.requests, "post", fake_post)
    result = speech.transcribe_audio(b"audio bytes")  # must not raise
    assert result.startswith(speech.TRANSCRIBE_ERROR_PREFIX)


# ── transcribe_audio_detailed (verbose_json + word timestamps) ──────────────

def test_detailed_unavailable_without_api_key(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "")
    result = speech.transcribe_audio_detailed(b"fake audio bytes")
    assert result["is_error"] is True
    assert result["text"].startswith(speech.TRANSCRIBE_ERROR_PREFIX)


def test_detailed_requests_verbose_json_with_word_timestamps(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "text": "This is my transcribed answer.",
                "duration": 4.2,
                "words": [{"word": "This", "start": 0.0, "end": 0.3}],
            }

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        assert data["response_format"] == "verbose_json"
        assert data["timestamp_granularities[]"] == "word"
        return FakeResponse()

    monkeypatch.setattr(speech.requests, "post", fake_post)
    result = speech.transcribe_audio_detailed(b"real-looking audio bytes")
    assert result["is_error"] is False
    assert result["text"] == "This is my transcribed answer."
    assert result["duration_seconds"] == 4.2
    assert result["words"] == [{"word": "This", "start": 0.0, "end": 0.3}]


def test_detailed_degrades_gracefully_without_words_or_duration(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"text": "Just plain text, no extras."}  # older/limited API response

    monkeypatch.setattr(speech.requests, "post", lambda *a, **kw: FakeResponse())
    result = speech.transcribe_audio_detailed(b"audio bytes")
    assert result["is_error"] is False
    assert result["text"] == "Just plain text, no extras."
    assert "duration_seconds" not in result
    assert "words" not in result


def test_detailed_empty_transcript_is_an_error(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"text": "   "}

    monkeypatch.setattr(speech.requests, "post", lambda *a, **kw: FakeResponse())
    result = speech.transcribe_audio_detailed(b"silence")
    assert result["is_error"] is True
    assert "no speech" in result["text"].lower()


def test_detailed_oversized_audio_rejected_without_network_call(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(speech, "MAX_AUDIO_BYTES", 10)
    result = speech.transcribe_audio_detailed(b"way more than ten bytes of fake audio")
    assert result["is_error"] is True


def test_detailed_timeout_handled_gracefully(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    def fake_post(*a, **kw):
        import requests
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(speech.requests, "post", fake_post)
    result = speech.transcribe_audio_detailed(b"audio bytes")
    assert result["is_error"] is True
    assert "timed out" in result["text"].lower()


def test_detailed_unexpected_exception_never_raises(monkeypatch):
    monkeypatch.setattr(speech, "GROQ_API_KEY", "gsk_fake")

    def fake_post(*a, **kw):
        raise RuntimeError("network is on fire")

    monkeypatch.setattr(speech.requests, "post", fake_post)
    result = speech.transcribe_audio_detailed(b"audio bytes")  # must not raise
    assert result["is_error"] is True
