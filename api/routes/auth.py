"""
Auth routes module.
Responsibility: User signup, login, current-user lookup, and interview
history for logged-in users.

Endpoints:
    POST /auth/signup   — Create an account
    POST /auth/login    — Exchange email+password for a JWT
    GET  /auth/me       — Current user, from the Authorization header
    GET  /auth/history  — Past final reports for the current user

Accounts require persistent storage (DATABASE_URL) — there's no meaningful
way to have a durable account backed only by in-memory state. If the
database isn't configured, these endpoints return a clear 503 rather than
silently pretending to work.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from models.schemas import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserHistoryResponse,
    UserReportItem,
    UserResponse,
)
from services import auth, db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


def _require_db():
    if not db.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Accounts require persistent storage, which isn't configured on this "
                   "server (DATABASE_URL is unset). Everything else in the app still works "
                   "without an account.",
        )


def get_current_user(authorization: str = Header(default="")) -> dict:
    """
    FastAPI dependency: extracts and validates the Bearer token, returns
    {user_id, email}. Raises 401 on anything wrong — missing header, bad
    scheme, expired/invalid token. Used by endpoints that require login.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    claims = auth.decode_access_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")
    return claims


def get_optional_user(authorization: str = Header(default="")) -> Optional[dict]:
    """
    Same as get_current_user but returns None instead of raising when no/invalid
    token is present — for endpoints (like /session/start) where login is
    optional and anonymous use must keep working exactly as before.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return auth.decode_access_token(token)


@router.post("/signup", response_model=TokenResponse)
def signup(request: SignupRequest):
    _require_db()
    password_hash = auth.hash_password(request.password)
    try:
        user = db.create_user(request.email, password_hash, request.name)
    except Exception:
        logger.exception("auth: signup failed for %s", request.email)
        raise HTTPException(status_code=503, detail="Could not create the account right now. Try again shortly.")
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    token = auth.create_access_token(user["id"], user["email"])
    logger.info("auth: signed up user %s", user["id"])
    return TokenResponse(access_token=token, user=UserResponse(**user))


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    _require_db()
    try:
        user = db.get_user_by_email(request.email.strip().lower())
    except Exception:
        logger.exception("auth: login lookup failed for %s", request.email)
        raise HTTPException(status_code=503, detail="Could not reach the account database right now.")
    if user is None or not auth.verify_password(request.password, user["password_hash"]):
        # Same error for "no such user" and "wrong password" — don't leak which one.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = auth.create_access_token(user["id"], user["email"])
    logger.info("auth: logged in user %s", user["id"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user["id"], email=user["email"], name=user["name"]),
    )


@router.get("/me", response_model=UserResponse)
def me(current=Depends(get_current_user)):
    user = db.get_user_by_id(current["user_id"])
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserResponse(**user)


@router.get("/history", response_model=UserHistoryResponse)
def history(current=Depends(get_current_user)):
    reports = db.get_user_reports(current["user_id"])
    return UserHistoryResponse(reports=[UserReportItem(**r) for r in reports])
