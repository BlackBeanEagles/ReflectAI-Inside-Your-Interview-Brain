"""
Auth module — password hashing and JWT issuance/verification.

Design notes:
    - Passwords are hashed with bcrypt (via the `bcrypt` package directly,
      not passlib — passlib's bcrypt backend has had maintenance issues).
      Plaintext passwords are never stored or logged anywhere.
    - Tokens are stateless JWTs signed with JWT_SECRET_KEY. If that env var
      isn't set, a random secret is generated at process startup — auth still
      works, but every token becomes invalid on the next restart (all users
      get logged out). That's a real, deliberate trade-off for zero-config
      local dev; production deployments should set JWT_SECRET_KEY explicitly
      so restarts don't silently log everyone out.
    - Unlike most of this codebase's "best-effort, never break the request"
      philosophy, auth failures are NOT swallowed — a wrong password or an
      invalid token must produce a clear 401, not a silent fallback.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import bcrypt
import jwt

logger = logging.getLogger(__name__)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "auth: JWT_SECRET_KEY is not set — generated a random one for this process. "
        "Every login token will become invalid the next time this process restarts. "
        "Set JWT_SECRET_KEY explicitly in production."
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "168"))  # 7 days


def mask_email(email: str) -> str:
    """
    Redact an email address for logging: keep enough to recognize/search for
    in a support conversation, hide the rest. Log lines flow to a shared
    platform log aggregator (see DEPLOY.md) regardless of whether
    DATABASE_URL/consent means the email is stored anywhere else, so it
    should never appear there in full.
    """
    local, _, domain = (email or "").partition("@")
    if not domain:
        return "***"
    visible = local[:2]
    return f"{visible}***@{domain}"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        # A malformed stored hash must fail closed, not raise into the caller.
        logger.exception("auth: password verification raised — treating as mismatch.")
        return False


def create_access_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict]:
    """Returns {user_id, email} if the token is valid and unexpired, else None."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return {"user_id": int(payload["sub"]), "email": payload["email"]}
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        logger.exception("auth: unexpected error decoding token.")
        return None


# ─── Password reset tokens ──────────────────────────────────────────────────
# Unlike the JWT session token above, a reset token is a one-time, short-lived
# secret that gets emailed in plaintext (in the reset link) and must remain
# usable even if the JWT_SECRET_KEY rotates or the process restarts — so it's
# a random high-entropy string, independently generated and stored (hashed)
# in the password_resets table, not a JWT.
PASSWORD_RESET_TOKEN_BYTES = 32
PASSWORD_RESET_EXPIRY_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRY_MINUTES", "60"))


def generate_reset_token() -> str:
    """A random URL-safe token to email to the user — never stored raw."""
    return secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)


def hash_reset_token(token: str) -> str:
    """
    SHA-256 of the token, for DB storage/lookup.

    Deliberately NOT bcrypt: bcrypt's slow, salted hashing exists to defend
    against brute-forcing a low-entropy human password. This token is already
    a 32-byte random secret (2^256 possibilities) — a fast, unsalted
    cryptographic hash is the standard, sufficient approach here, and lets
    lookup be a plain indexed equality query instead of needing to check
    every stored hash with bcrypt.checkpw.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
