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
import time
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
    """
    Create tables if they don't exist. No-op if DATABASE_URL is unset.

    Retries a few times with a longer per-attempt timeout than normal request
    queries get: a free-tier Neon compute that has scaled to zero (or a
    brand-new project) can take several seconds to wake up for its very first
    connection. This only runs once at process startup, so paying extra
    latency here is cheap — but failing here is not: every other function in
    this module only checks is_enabled() (DATABASE_URL is set), not whether
    init_db() actually succeeded, so a single slow wakeup here used to
    permanently disable persistence for the process's whole lifetime with
    "relation does not exist" errors on every query.
    """
    if not DATABASE_URL:
        logger.info("db: DATABASE_URL not set — running without persistent storage.")
        return

    attempts = 4
    init_timeout_s = max(DB_CONNECT_TIMEOUT_S, 10)
    last_error: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        try:
            from psycopg_pool import ConnectionPool
            with ConnectionPool(
                DATABASE_URL,
                min_size=0,
                max_size=1,
                open=True,
                timeout=init_timeout_s,
                kwargs={"connect_timeout": init_timeout_s},
            ) as init_pool:
                with init_pool.connection() as conn:
                    _create_schema(conn)
            logger.info("db: tables ready (attempt %d/%d).", attempt, attempts)
            return
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                wait_s = 2 * attempt
                logger.warning(
                    "db: init_db attempt %d/%d failed (%s) — retrying in %ds.",
                    attempt, attempts, exc, wait_s,
                )
                time.sleep(wait_s)

    logger.error(
        "db: init_db failed after %d attempts — persistence disabled for this process. Last error: %s",
        attempts, last_error,
    )


def _create_schema(conn) -> None:
    """Run the CREATE TABLE / migration statements. Raises on failure — the
    caller (init_db) owns retry and error-swallowing policy."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
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
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
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
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            report JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    # Existing databases created before user_id existed won't have the
    # column — add it defensively so upgrading doesn't require a
    # manual migration step.
    for table in ("resumes", "interactions", "reports"):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id "
            f"INTEGER REFERENCES users(id) ON DELETE SET NULL"
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resumes_session ON resumes(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_session ON reports(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")


def save_resume(session_id: str, raw_text: Optional[str], cleaned: Dict, user_id: Optional[int] = None) -> None:
    """Persist a parsed resume tied to a session_id (and a user, if logged in). Best-effort."""
    pool = _get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO resumes (session_id, user_id, raw_text, skills, projects, experience)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    user_id,
                    raw_text,
                    json.dumps(cleaned.get("skills", [])),
                    json.dumps(cleaned.get("projects", [])),
                    json.dumps(cleaned.get("experience", [])),
                ),
            )
    except Exception:
        logger.exception("db: save_resume failed for session %s", session_id)


def save_interaction(session_id: str, interaction: Dict, user_id: Optional[int] = None) -> None:
    """Persist one evaluated Q&A interaction (and a user, if logged in). Best-effort."""
    pool = _get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO interactions
                    (session_id, user_id, question, answer, round_type, scores, final_score,
                     feedback, response_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    user_id,
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


def save_report(session_id: str, report: Dict, user_id: Optional[int] = None) -> None:
    """Persist a generated final report (and a user, if logged in). Best-effort."""
    pool = _get_pool()
    if pool is None:
        return
    try:
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO reports (session_id, user_id, report) VALUES (%s, %s, %s)",
                (session_id, user_id, json.dumps(report)),
            )
    except Exception:
        logger.exception("db: save_report failed for session %s", session_id)


# ── Users ────────────────────────────────────────────────────────────────────
# Unlike everything else in this module, user accounts are NOT best-effort —
# signup/login must fail loudly if the database is unavailable, since a
# silently-lost account creation would be far worse than a clear error. These
# raise on failure; callers (api/routes/auth.py) turn that into an HTTP error.

def create_user(email: str, password_hash: str, name: Optional[str] = None) -> Optional[Dict]:
    """
    Insert a new user. Returns the created user's {id, email, name} dict, or
    None if a user with this email already exists. Raises if the DB is
    unavailable — the caller must not report success it can't back up.
    """
    pool = _get_pool()
    if pool is None:
        raise RuntimeError("Persistent storage is not configured on this server.")
    with pool.connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
        if existing:
            return None
        row = conn.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s) "
            "RETURNING id, email, name",
            (email, password_hash, name),
        ).fetchone()
        return {"id": row[0], "email": row[1], "name": row[2]}


def get_user_by_email(email: str) -> Optional[Dict]:
    """Returns {id, email, password_hash, name} or None. Raises if DB unavailable."""
    pool = _get_pool()
    if pool is None:
        raise RuntimeError("Persistent storage is not configured on this server.")
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, name FROM users WHERE email = %s", (email,)
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "password_hash": row[2], "name": row[3]}


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Returns {id, email, name} or None. Best-effort (returns None on any failure)."""
    pool = _get_pool()
    if pool is None:
        return None
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT id, email, name FROM users WHERE id = %s", (user_id,)
            ).fetchone()
            if not row:
                return None
            return {"id": row[0], "email": row[1], "name": row[2]}
    except Exception:
        logger.exception("db: get_user_by_id failed for user %s", user_id)
        return None


def get_user_reports(user_id: int, limit: int = 20) -> List[Dict]:
    """Most recent final reports for a logged-in user. Best-effort — returns [] on failure."""
    pool = _get_pool()
    if pool is None:
        return []
    try:
        with pool.connection() as conn:
            rows = conn.execute(
                "SELECT session_id, report, created_at FROM reports "
                "WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            ).fetchall()
            return [
                {"session_id": r[0], "report": r[1], "created_at": r[2].isoformat()}
                for r in rows
            ]
    except Exception:
        logger.exception("db: get_user_reports failed for user %s", user_id)
        return []
