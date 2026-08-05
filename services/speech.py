"""
Speech module.
Responsibility: Speech-to-text via Groq's hosted Whisper endpoint.

This is deliberately independent of LLM_PROVIDER (utils/llm.py) — transcription
always goes through Groq, since Ollama has no audio model and running Whisper
locally would be a heavy new dependency (ffmpeg, a multi-GB model download)
that contradicts the whole "runs free" deployment story. If GROQ_API_KEY isn't
set, voice input is unavailable and callers should fall back to typing —
there is no local/offline path for this feature.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

MAX_AUDIO_MB = float(os.getenv("MAX_AUDIO_MB", "10"))
MAX_AUDIO_BYTES = int(MAX_AUDIO_MB * 1024 * 1024)

TRANSCRIBE_ERROR_PREFIX = "Transcription error"


def is_available() -> bool:
    return bool(GROQ_API_KEY)


def transcribe_audio(audio_bytes: bytes, filename: str = "answer.wav") -> str:
    """
    Transcribe recorded speech to text via Groq's Whisper API.

    Returns the transcript, or a string starting with TRANSCRIBE_ERROR_PREFIX
    on failure — never raises, matching the error-string convention
    utils.llm.call_llm uses so the frontend can detect failures the same way.
    """
    if not GROQ_API_KEY:
        return f"{TRANSCRIBE_ERROR_PREFIX}: GROQ_API_KEY is not set — voice input needs a Groq API key " \
               f"even if you're using Ollama for interview questions. Get a free key at console.groq.com."

    if not audio_bytes:
        return f"{TRANSCRIBE_ERROR_PREFIX}: No audio received."

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return f"{TRANSCRIBE_ERROR_PREFIX}: Recording too large (max {MAX_AUDIO_MB:.0f}MB). Try a shorter answer."

    try:
        response = requests.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={"file": (filename, audio_bytes)},
            data={"model": GROQ_WHISPER_MODEL, "response_format": "text"},
            timeout=30,
        )
        response.raise_for_status()
        text = response.text.strip()
        if not text:
            return f"{TRANSCRIBE_ERROR_PREFIX}: No speech detected in the recording."
        logger.info("speech: transcribed %d bytes of audio -> %d chars of text", len(audio_bytes), len(text))
        return text
    except requests.exceptions.Timeout:
        logger.error("speech: transcription timed out")
        return f"{TRANSCRIBE_ERROR_PREFIX}: Transcription timed out. Try again."
    except requests.exceptions.HTTPError as e:
        logger.error("speech: transcription HTTP error: %s", e)
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        return f"{TRANSCRIBE_ERROR_PREFIX}: {detail or str(e)}"
    except Exception as e:
        logger.exception("speech: unexpected transcription failure")
        return f"{TRANSCRIBE_ERROR_PREFIX}: Unexpected error — {e}"
