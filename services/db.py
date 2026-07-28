"""
Database module — optional persistent storage for resumes and interview history.

Storage is Postgres (designed for Neon's free tier, but any Postgres works) via
DATABASE_URL. Persistence is entirely optional and best-effort:

    - If DATABASE_URL is not set, every function here is a no-op. The app runs
      exactly as before (in-memory only) with zero behavior change.
    - If DATABASE_URL is set but a write fails (network blip, DB asleep, etc.),
      the error is logged and swallowed. Persisting a record must never break
      the interview flow for the person using the app right now.

A single small connection pool is shared across requests; FastAPI's lifespan
calls init_db() once at startup to create tables if they don't exist yet.
"""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

_pool = None


def is_enabled() -> bool:
    return bool(DATABASE_URL)


# A slow/unreachable database must degrade to "skip persistence" in a couple
# of seconds, not hang the request — connect_timeout bounds how long a single
# TCP/handshake attempt can take, and the pool's own `timeout` bounds how long
# a caller waits for a connection to become available at all (min_size=0 and
# open=False mean the pool never blocks trying to eagerly open connections;
# it only tries when something actually asks for one).
DB_CONNECT_TIMEOUT_S = int(os.getenv("DB_CONNECT_TIMEOUT_S", "3"))


def _get_pool():
    """Lazily create the connection pool on first use."""
    global _pool
    if _pool is not None:
        return _pool
    if not DATABASE_URL:
        return None
    try:
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=0,
            max_size=5,
            open=False,
            timeout=DB_CONNECT_TIMEOUT_S,
            kwargs={"connect_timeout": DB_CONNECT_TIMEOUT_S},
        )
        _pool.open(wait=False)
        return _pool
    except Exception:
        logger.exception("db: failed to create connection pool — persistence disabled for this process.")
        return None


def init_db() -> None:
    """Create tables if they don't exist. No-op if DATABASE_URL is unset."""
    pool = _get_pool()
    if pool is None:
        if DATABASE_URL:
            logger.warning("db: DATABASE_URL is set but the pool failed to initialize.")
        else:
            logger.info("db: DATABASE_URL not set — running without persistent storage.")
        return
    try:
        with pool.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    raw_text TEXT,
                    skills JSONB,
                    projects JSONB,
                    experience JSONB,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    question TEXT,
                    answer TEXT,
                    round_type TEXT,
                    scores JSONB,
                    final_score REAL,
                    feedback JSONB,
                    response_time_seconds REAL,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    report JSONB,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resumes_session ON resumes(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_session ON reports(session_id)")
        logger.info("db: tables ready.")
    except Exception:
        logger.exception("db: init_db failed — persistence disabled for this process.")


def save_resume(session_id: str, raw_text: Optional[str], cleaned: Dict) -> None:
    """Persist a parsed resume tied to a session_id. Best-effort."""
    pool = _get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO resumes (session_id, raw_text, skills, projects, experience)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    raw_text,
                    json.dumps(cleaned.get("skills", [])),
                    json.dumps(cleaned.get("projects", [])),
                    json.dumps(cleaned.get("experience", [])),
                ),
            )
    except Exception:
        logger.exception("db: save_resume failed for session %s", session_id)


def save_interaction(session_id: str, interaction: Dict) -> None:
    """Persist one evaluated Q&A interaction. Best-effort."""
    pool = _get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO interactions
                    (session_id, question, answer, round_type, scores, final_score,
                     feedback, response_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    interaction.get("question"),
                    interaction.get("answer"),
                    interaction.get("round"),
                    json.dumps(interaction.get("scores", {})),
                    interaction.get("final_score"),
                    json.dumps(interaction.get("feedback", {})),
                    interaction.get("response_time_seconds"),
                ),
            )
    except Exception:
        logger.exception("db: save_interaction failed for session %s", session_id)


def save_report(session_id: str, report: Dict) -> None:
    """Persist a generated final report. Best-effort."""
    pool = _get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO reports (session_id, report) VALUES (%s, %s)",
                (session_id, json.dumps(report)),
            )
    except Exception:
        logger.exception("db: save_report failed for session %s", session_id)
