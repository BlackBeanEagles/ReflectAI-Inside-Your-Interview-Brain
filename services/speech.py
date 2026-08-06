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
from typing import Dict

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


def transcribe_audio_detailed(audio_bytes: bytes, filename: str = "answer.wav") -> Dict:
    """
    Same transcription as transcribe_audio(), but requests Groq's
    verbose_json format to also get audio duration and (when the model
    supports it) per-word timestamps — the raw material
    services/voice_analysis.py needs for pace and pause detection.

    Always returns {"text": str, "is_error": bool}, plus "duration_seconds"
    and/or "words" when Groq actually provided them. Their absence must be
    treated as "couldn't measure this", never assumed to mean zero — that
    distinction is what lets voice_analysis degrade gracefully instead of
    fabricating pace/pause numbers it has no basis for.
    """
    if not GROQ_API_KEY:
        return {
            "text": f"{TRANSCRIBE_ERROR_PREFIX}: GROQ_API_KEY is not set — voice input needs a Groq "
                    f"API key even if you're using Ollama for interview questions. "
                    f"Get a free key at console.groq.com.",
            "is_error": True,
        }
    if not audio_bytes:
        return {"text": f"{TRANSCRIBE_ERROR_PREFIX}: No audio received.", "is_error": True}
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return {
            "text": f"{TRANSCRIBE_ERROR_PREFIX}: Recording too large (max {MAX_AUDIO_MB:.0f}MB). "
                    f"Try a shorter answer.",
            "is_error": True,
        }

    try:
        response = requests.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={"file": (filename, audio_bytes)},
            data={
                "model": GROQ_WHISPER_MODEL,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        text = (payload.get("text") or "").strip()
        if not text:
            return {"text": f"{TRANSCRIBE_ERROR_PREFIX}: No speech detected in the recording.", "is_error": True}

        result: Dict = {"text": text, "is_error": False}
        duration = payload.get("duration")
        if isinstance(duration, (int, float)):
            result["duration_seconds"] = float(duration)
        words = payload.get("words")
        if isinstance(words, list) and words:
            result["words"] = words

        logger.info(
            "speech: transcribed %d bytes of audio -> %d chars (detailed, duration=%s, words=%s)",
            len(audio_bytes), len(text), result.get("duration_seconds"), len(words) if isinstance(words, list) else None,
        )
        return result
    except requests.exceptions.Timeout:
        logger.error("speech: detailed transcription timed out")
        return {"text": f"{TRANSCRIBE_ERROR_PREFIX}: Transcription timed out. Try again.", "is_error": True}
    except requests.exceptions.HTTPError as e:
        logger.error("speech: detailed transcription HTTP error: %s", e)
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        return {"text": f"{TRANSCRIBE_ERROR_PREFIX}: {detail or str(e)}", "is_error": True}
    except Exception as e:
        logger.exception("speech: unexpected detailed transcription failure")
        return {"text": f"{TRANSCRIBE_ERROR_PREFIX}: Unexpected error — {e}", "is_error": True}
