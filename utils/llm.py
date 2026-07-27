"""
LLM utility module.
Responsibility: Talk to an LLM backend and return a response string.

Two backends are supported behind one interface, selected by LLM_PROVIDER:
    * "ollama" (default) — local model via Ollama's HTTP API. Free, but needs
      a GPU/enough RAM on whatever machine runs it — not viable on free web
      hosting tiers (Render/Railway free plans cap around 512MB-1GB RAM).
    * "groq"   — Groq's hosted API (OpenAI-compatible chat/completions).
      Free tier, no card required, and fast enough that it's the recommended
      backend for a publicly hosted deployment. Set GROQ_API_KEY.

Call sites never know which backend is active — they call call_llm(prompt,
purpose=...) exactly the same way either way.

Latency notes (why this module looks the way it does):
    * ``keep_alive`` (Ollama only) stops the model being evicted between
      requests. Without it, any idle gap pays a full model load again.
    * Every profile caps output length per task. Unbounded generation was the
      single biggest cost — the model would happily write 800 tokens where the
      parser only reads 6 lines.
    * A pooled ``requests.Session`` reuses the TCP/TLS connection instead of
      doing a fresh handshake per call.
    * ``stop`` sequences end generation the moment the useful part is done.
"""

import logging
import os
import threading
import time
from typing import Dict, Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

# ── Ollama config (local dev) ─────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_URL = f"{OLLAMA_HOST}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# Context window. llama3 supports 8k but we never send anything near that, and a
# smaller window means a smaller KV cache and noticeably faster prompt eval.
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))

# ── Groq config (free hosted inference) ───────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Model name surfaced to /health and the frontend status strip, regardless of
# which provider is active.
MODEL = GROQ_MODEL if PROVIDER == "groq" else OLLAMA_MODEL

DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60" if PROVIDER == "groq" else "180"))


# ─── Per-task generation profiles ─────────────────────────────────────────────
# Each call site declares its purpose; the profile caps tokens and picks a
# sampling temperature appropriate to the task. Token caps are sized from the
# actual output each parser needs, with headroom.
#
# Stop sequences only match "\n" followed by a digit and a period (a numbered
# list item starting a new line) — never a bare "2." anywhere in the text.
# An earlier version stopped on any "2." substring, which also matched things
# like "O(n^2)." or "12.5%" mid-answer and truncated legitimate output.

PROFILES: Dict[str, Dict] = {
    # A single interview question — one sentence. Never needs more.
    "question": {
        "num_predict": 100,
        "temperature": 0.8,
        "top_k": 30,
        "top_p": 0.9,
        "stop": ["\n\n", "\nQuestion 2", "\n2."],
    },
    # Structured rubric block: N score lines + 3 feedback sentences.
    "evaluation": {
        "num_predict": 260,
        "temperature": 0.2,
        "top_k": 20,
        "top_p": 0.85,
        "stop": ["\n\n\n"],
    },
    # Final report — the longest legitimate output in the app.
    "report": {
        "num_predict": 600,
        "temperature": 0.4,
        "top_k": 40,
        "top_p": 0.9,
    },
    # Short narrative paragraphs (cognitive coach, replay comparison).
    "coach": {
        "num_predict": 200,
        "temperature": 0.5,
        "top_k": 40,
        "top_p": 0.9,
    },
    "default": {
        "num_predict": 300,
        "temperature": 0.6,
    },
}

# Purposes whose output is safe to memoise. Question generation is excluded on
# purpose — identical prompts should still produce varied questions.
CACHEABLE = {"evaluation", "report", "coach"}
_CACHE_MAX = 128


# ─── Connection pooling ───────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=0)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


_session = _build_session()
_cache: "dict[tuple, str]" = {}
_cache_lock = threading.Lock()
_warm_lock = threading.Lock()
_warmed = False


def _cache_get(key) -> Optional[str]:
    with _cache_lock:
        return _cache.get(key)


def _cache_put(key, value: str) -> None:
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[key] = value


def clear_cache() -> None:
    """Drop the memoised responses. Used by tests."""
    with _cache_lock:
        _cache.clear()


# ─── Ollama backend ───────────────────────────────────────────────────────────

def _ollama_options(purpose: str) -> Dict:
    profile = dict(PROFILES.get(purpose, PROFILES["default"]))
    profile.pop("stop", None)
    profile["num_ctx"] = NUM_CTX
    return profile


def _call_ollama(prompt: str, purpose: str, timeout: int) -> Dict:
    """Returns {"ok": bool, "text": str, "meta": dict} — never raises."""
    profile = PROFILES.get(purpose, PROFILES["default"])
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": _ollama_options(purpose),
        }
        if profile.get("stop"):
            payload["options"]["stop"] = profile["stop"]

        response = _session.post(OLLAMA_URL, json=payload, timeout=timeout)
        if response.status_code != 200:
            return {"ok": False, "text": (
                f"LLM error: Ollama returned status {response.status_code} — {response.text[:200]}"
            )}

        data = response.json()
        return {
            "ok": True,
            "text": data.get("response", "").strip(),
            "meta": {
                "eval_count": data.get("eval_count"),
                "load_s": (data.get("load_duration") or 0) / 1e9,
            },
        }
    except requests.exceptions.ConnectionError:
        return {"ok": False, "text": "Ollama is not running. Start it with: .\\start_ollama.bat"}
    except requests.exceptions.Timeout:
        return {"ok": False, "text": f"LLM request timed out after {timeout} seconds."}
    except Exception as e:
        return {"ok": False, "text": f"Unexpected error calling LLM: {str(e)}"}


# ─── Groq backend ─────────────────────────────────────────────────────────────

def _call_groq(prompt: str, purpose: str, timeout: int) -> Dict:
    """Returns {"ok": bool, "text": str, "meta": dict} — never raises."""
    if not GROQ_API_KEY:
        return {"ok": False, "text": (
            "LLM error: GROQ_API_KEY is not set. Get a free key at "
            "console.groq.com and set it as an environment variable."
        )}

    profile = PROFILES.get(purpose, PROFILES["default"])
    try:
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": profile.get("num_predict", 300),
            "temperature": profile.get("temperature", 0.6),
            "top_p": profile.get("top_p", 0.9),
        }
        if profile.get("stop"):
            payload["stop"] = profile["stop"][:4]  # Groq caps stop sequences at 4

        response = _session.post(
            GROQ_URL,
            json=payload,
            timeout=timeout,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
        if response.status_code == 429:
            return {"ok": False, "text": (
                "LLM error: Groq rate limit reached. Please wait a moment and try again."
            )}
        if response.status_code != 200:
            return {"ok": False, "text": (
                f"LLM error: Groq returned status {response.status_code} — {response.text[:200]}"
            )}

        data = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return {
            "ok": True,
            "text": text.strip(),
            "meta": {"eval_count": usage.get("completion_tokens"), "load_s": 0.0},
        }
    except requests.exceptions.ConnectionError:
        return {"ok": False, "text": "Unexpected error calling LLM: could not reach Groq."}
    except requests.exceptions.Timeout:
        return {"ok": False, "text": f"LLM request timed out after {timeout} seconds."}
    except Exception as e:
        return {"ok": False, "text": f"Unexpected error calling LLM: {str(e)}"}


def _dispatch(prompt: str, purpose: str, timeout: int) -> Dict:
    return _call_groq(prompt, purpose, timeout) if PROVIDER == "groq" else _call_ollama(prompt, purpose, timeout)


# ─── Main entry point ─────────────────────────────────────────────────────────

def call_llm(
    prompt: str,
    purpose: str = "default",
    timeout: int = DEFAULT_TIMEOUT,
    use_cache: bool = True,
) -> str:
    """
    Sends a prompt to the active LLM backend (Ollama or Groq).
    Returns the generated text as a string.
    Handles errors gracefully — never crashes the API.

    Args:
        prompt:    The full prompt to send.
        purpose:   One of PROFILES — selects token cap and sampling settings.
                   Getting this right is the main latency lever in the app.
        timeout:   Seconds before giving up.
        use_cache: Memoise identical prompts for cacheable purposes.
    """
    key = (PROVIDER, MODEL, purpose, prompt)

    if use_cache and purpose in CACHEABLE:
        hit = _cache_get(key)
        if hit is not None:
            logger.info("LLM cache hit (purpose=%s)", purpose)
            return hit

    started = time.perf_counter()
    result = _dispatch(prompt, purpose, timeout)
    elapsed = time.perf_counter() - started

    if not result["ok"]:
        logger.error("LLM error (provider=%s, purpose=%s): %s", PROVIDER, purpose, result["text"])
        return result["text"]

    meta = result.get("meta", {})
    logger.info(
        "LLM provider=%s purpose=%s took %.2fs (tokens=%s, load=%.2fs)",
        PROVIDER, purpose, elapsed, meta.get("eval_count"), meta.get("load_s", 0.0),
    )

    text = result["text"]
    if not text:
        return "LLM returned an empty response. Try again."

    if use_cache and purpose in CACHEABLE:
        _cache_put(key, text)

    return text


def stream_llm(
    prompt: str,
    purpose: str = "default",
    timeout: int = DEFAULT_TIMEOUT,
) -> Iterator[str]:
    """
    Yield token chunks as the model produces them (Ollama only — Groq streaming
    is not wired up since the app currently reads full responses everywhere).

    Total generation time is unchanged, but the user sees the first words in
    well under a second instead of staring at a spinner for the whole run.
    On error, yields a single error string (same prefixes as ``call_llm``).
    """
    if PROVIDER != "ollama":
        yield call_llm(prompt, purpose=purpose, timeout=timeout)
        return

    profile = PROFILES.get(purpose, PROFILES["default"])
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": _ollama_options(purpose),
    }
    if profile.get("stop"):
        payload["options"]["stop"] = profile["stop"]

    try:
        with _session.post(OLLAMA_URL, json=payload, timeout=timeout, stream=True) as resp:
            if resp.status_code != 200:
                yield f"LLM error: Ollama returned status {resp.status_code}"
                return
            import json as _json
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = _json.loads(line)
                except ValueError:
                    continue
                piece = chunk.get("response", "")
                if piece:
                    yield piece
                if chunk.get("done"):
                    return
    except requests.exceptions.ConnectionError:
        yield "Ollama is not running. Start it with: .\\start_ollama.bat"
    except requests.exceptions.Timeout:
        yield f"LLM request timed out after {timeout} seconds."
    except Exception as e:
        yield f"Unexpected error calling LLM: {str(e)}"


# ─── Warm-up ──────────────────────────────────────────────────────────────────

def warmup(blocking: bool = False) -> None:
    """
    Load the model into memory ahead of the first real request (Ollama only —
    Groq is a stateless hosted API with nothing to warm).

    The first generation of a session otherwise pays the full model-load cost
    on top of generation. Called at API startup.
    """
    global _warmed

    if PROVIDER != "ollama":
        return

    def _run():
        global _warmed
        with _warm_lock:
            if _warmed:
                return
            try:
                started = time.perf_counter()
                _session.post(
                    OLLAMA_URL,
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": "ok",
                        "stream": False,
                        "keep_alive": KEEP_ALIVE,
                        "options": {"num_predict": 1, "num_ctx": NUM_CTX},
                    },
                    timeout=300,
                )
                _warmed = True
                logger.info("LLM warm-up complete in %.1fs (%s)",
                            time.perf_counter() - started, OLLAMA_MODEL)
            except Exception as exc:
                logger.warning("LLM warm-up skipped: %s", exc)

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, name="llm-warmup", daemon=True).start()


def is_ready() -> Dict:
    """
    Report backend readiness for /health.

    Ollama: probes /api/ps to see if the model is actually resident in memory.
    Groq:   there's no model to warm — "ready" just means a key is configured.
    """
    if PROVIDER == "groq":
        return {"reachable": True, "model_loaded": bool(GROQ_API_KEY),
                "detail": None if GROQ_API_KEY else "GROQ_API_KEY not set"}
    try:
        r = _session.get(f"{OLLAMA_HOST}/api/ps", timeout=1)
        if r.status_code == 200:
            loaded = [m.get("name", "") for m in r.json().get("models", [])]
            model_loaded = any(
                name == OLLAMA_MODEL or name.startswith(OLLAMA_MODEL.split(":")[0])
                for name in loaded
            )
            return {"reachable": True, "model_loaded": model_loaded, "detail": None}
        return {"reachable": False, "model_loaded": False, "detail": f"status {r.status_code}"}
    except Exception as exc:
        return {"reachable": False, "model_loaded": False, "detail": str(exc)}


def call_llm_parallel(jobs: List[Dict]) -> List[str]:
    """
    Run several independent prompts concurrently.

    For Ollama, generation is serialised for a single model unless
    OLLAMA_NUM_PARALLEL is raised, but this still removes Python-side
    round-trip stacking. For Groq, requests genuinely run in parallel.
    Results come back in the same order as ``jobs``.
    """
    from concurrent.futures import ThreadPoolExecutor

    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
        return list(pool.map(lambda j: call_llm(**j), jobs))
