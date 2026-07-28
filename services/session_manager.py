"""
Session Manager module — Week 3 Day 5.
Responsibility: Store and manage interview session history in-memory.

Every evaluated answer is stored as one "interaction" with this structure:
    {
        "question":    str,
        "answer":      str,
        "round":       "hr" | "technical" | "stress",
        "scores":      { dimension_name: score (float) },
        "final_score": float,
        "feedback": {
            "strength":    str,
            "weakness":    str,
            "improvement": str,
        },
        "timestamp": ISO-8601 UTC string,
        "response_time_seconds": optional float (Week 5 — impulsivity model),
    }

Sessions are keyed by a UUID session_id.
Storage is in-memory (dict) — fast, simple, sufficient for a single-process
deployment. Two things a hosted, publicly-reachable instance needs that a
local dev run didn't:

    1. Sessions never expired. On a long-running free-tier host, every visitor
       who ever loads the page leaves a session in memory forever — an
       unbounded, permanent memory leak. SESSION_TTL_MINUTES now evicts idle
       sessions, and MAX_SESSIONS caps total memory use by dropping the oldest
       session once the cap is hit (values are load-bearing, not decorative).
    2. All state lives in one process's memory, so this only works correctly
       with a single worker/instance. Scaling to multiple instances would need
       a shared store (Redis, a database) — out of scope while running free.

Day 6 (report_generator.py) reads from this module to build the final report.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "180"))
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "500"))

# ── In-memory store ────────────────────────────────────────────────────────────
# session_id (str) → list of interaction dicts
# session_id (str) → last-touched monotonic-ish timestamp (for eviction)

_sessions: Dict[str, List[Dict]] = {}
_last_touched: Dict[str, float] = {}
_store_consent: Dict[str, bool] = {}
_lock = threading.Lock()


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _evict_expired_locked() -> None:
    """Drop sessions idle longer than SESSION_TTL_MINUTES. Caller holds _lock."""
    cutoff = _now() - (SESSION_TTL_MINUTES * 60)
    expired = [sid for sid, ts in _last_touched.items() if ts < cutoff]
    for sid in expired:
        _sessions.pop(sid, None)
        _last_touched.pop(sid, None)
        _store_consent.pop(sid, None)
    if expired:
        logger.info("session_manager: Evicted %d expired session(s).", len(expired))


def _evict_oldest_if_over_capacity_locked() -> None:
    """Caller holds _lock."""
    while len(_sessions) > MAX_SESSIONS:
        oldest_sid = min(_last_touched, key=_last_touched.get, default=None)
        if oldest_sid is None:
            break
        _sessions.pop(oldest_sid, None)
        _last_touched.pop(oldest_sid, None)
        _store_consent.pop(oldest_sid, None)
        logger.warning(
            "session_manager: MAX_SESSIONS (%d) exceeded — evicted oldest session %s.",
            MAX_SESSIONS, oldest_sid,
        )


def _touch_locked(session_id: str) -> None:
    _last_touched[session_id] = _now()


# ── Session lifecycle ──────────────────────────────────────────────────────────

def create_session(store_consent: bool = False) -> str:
    """
    Create a new empty session.

    Args:
        store_consent: Whether the user explicitly agreed to have their
            resume/answers persisted to the database (see services/db.py).
            Defaults to False — persistence requires an opt-in, enforced here
            rather than trusted to the frontend, since add_interaction() is
            also called directly by API clients.

    Returns:
        session_id (UUID string) — store this on the client side.
    """
    session_id = str(uuid.uuid4())
    with _lock:
        _evict_expired_locked()
        _sessions[session_id] = []
        _store_consent[session_id] = bool(store_consent)
        _touch_locked(session_id)
        _evict_oldest_if_over_capacity_locked()
    logger.info(
        "session_manager: Created session %s (store_consent=%s)", session_id, store_consent
    )
    return session_id


def has_store_consent(session_id: str) -> bool:
    """Whether this session opted in to persistent storage."""
    with _lock:
        return _store_consent.get(session_id, False)


def reset_session(session_id: str) -> None:
    """
    Clear all interactions for the given session (keeps the session_id alive).
    Creates the session if it does not exist.
    """
    with _lock:
        _sessions[session_id] = []
        _touch_locked(session_id)
    logger.info("session_manager: Reset session %s", session_id)


def session_exists(session_id: str) -> bool:
    """Return True if the session_id is known to this store."""
    with _lock:
        return session_id in _sessions


# ── Interaction storage ────────────────────────────────────────────────────────

def add_interaction(
    session_id: str,
    question: str,
    answer: str,
    round_type: str,
    scores: Dict[str, float],
    final_score: float,
    feedback: Dict[str, str],
    response_time_seconds: Optional[float] = None,
) -> Dict:
    """
    Store one evaluated interaction into the session.

    Automatically creates the session if session_id is unknown (fault-tolerant).

    Args:
        session_id:  Session identifier returned by create_session().
        question:    The interview question that was asked.
        answer:      The candidate's answer.
        round_type:  "hr", "technical", or "stress".
        scores:      Per-dimension scores from the evaluator.
        final_score: Average score from the evaluator.
        feedback:    Dict with keys strength / weakness / improvement.
        response_time_seconds: Optional wall time to answer (Week 5 Day 2).

    Returns:
        The stored interaction dict (including timestamp).
    """
    interaction: Dict = {
        "question":    question,
        "answer":      answer,
        "round":       round_type.lower().strip(),
        "scores":      scores,
        "final_score": final_score,
        "feedback":    feedback,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }
    if response_time_seconds is not None:
        interaction["response_time_seconds"] = float(response_time_seconds)

    with _lock:
        if session_id not in _sessions:
            logger.warning(
                "session_manager: Unknown session %s — creating automatically.", session_id
            )
            _sessions[session_id] = []
        _sessions[session_id].append(interaction)
        _touch_locked(session_id)
        total = len(_sessions[session_id])

    logger.info(
        "session_manager: Added interaction to session %s "
        "(total=%d, round=%s, score=%.1f)",
        session_id,
        total,
        round_type,
        final_score,
    )

    return interaction


# ── Session retrieval ──────────────────────────────────────────────────────────

def get_session(session_id: str) -> List[Dict]:
    """
    Return a copy of the full interaction history for the given session.
    Returns an empty list if the session_id is not found.
    """
    with _lock:
        return list(_sessions.get(session_id, []))


def get_session_count(session_id: str) -> int:
    """Return the number of interactions stored in the session."""
    with _lock:
        return len(_sessions.get(session_id, []))


def active_session_count() -> int:
    """Return the number of non-expired sessions currently held in memory."""
    with _lock:
        return len(_sessions)
