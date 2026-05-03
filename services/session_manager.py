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
Storage is in-memory (dict) — fast, simple, sufficient for Week 3.

Day 6 (report_generator.py) reads from this module to build the final report.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── In-memory store ────────────────────────────────────────────────────────────
# session_id (str) → list of interaction dicts

_sessions: Dict[str, List[Dict]] = {}


# ── Session lifecycle ──────────────────────────────────────────────────────────

def create_session() -> str:
    """
    Create a new empty session.

    Returns:
        session_id (UUID string) — store this on the client side.
    """
    session_id = str(uuid.uuid4())
    _sessions[session_id] = []
    logger.info("session_manager: Created session %s", session_id)
    return session_id


def reset_session(session_id: str) -> None:
    """
    Clear all interactions for the given session (keeps the session_id alive).
    Creates the session if it does not exist.
    """
    _sessions[session_id] = []
    logger.info("session_manager: Reset session %s", session_id)


def session_exists(session_id: str) -> bool:
    """Return True if the session_id is known to this store."""
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
    if session_id not in _sessions:
        logger.warning(
            "session_manager: Unknown session %s — creating automatically.", session_id
        )
        _sessions[session_id] = []

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

    _sessions[session_id].append(interaction)

    logger.info(
        "session_manager: Added interaction to session %s "
        "(total=%d, round=%s, score=%.1f)",
        session_id,
        len(_sessions[session_id]),
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
    return list(_sessions.get(session_id, []))


def get_session_count(session_id: str) -> int:
    """Return the number of interactions stored in the session."""
    return len(_sessions.get(session_id, []))
