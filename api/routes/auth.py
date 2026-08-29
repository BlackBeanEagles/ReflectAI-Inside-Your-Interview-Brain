"""
Auth routes module.
Responsibility: User signup, login, current-user lookup, password reset,
and interview history for logged-in users.

Endpoints:
    POST /auth/signup            — Create an account
    POST /auth/login             — Exchange email+password for a JWT
    GET  /auth/me                — Current user, from the Authorization header
    GET  /auth/history           — Past final reports for the current user
    POST /auth/forgot-password   — Request a password reset email
    POST /auth/reset-password    — Consume a reset token, set a new password

Accounts require persistent storage (DATABASE_URL) — there's no meaningful
way to have a durable account backed only by in-memory state. If the
database isn't configured, these endpoints return a clear 503 rather than
silently pretending to work.

Password reset additionally requires RESEND_API_KEY (see services/email.py).
Without it, /auth/forgot-password still returns its generic success message
(never reveals whether the email send actually worked — see
ForgotPasswordResponse) but no email is actually sent; check server logs.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from models.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignupRequest,
    TokenResponse,
    UserHistoryResponse,
    UserReportItem,
    UserResponse,
)
from services import auth, db, email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# Used to build the link inside the reset email — a Streamlit app doesn't
# have server-side routing, so the link just opens the app with a query
# param (?reset_token=...) that the frontend reads via st.query_params.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:8501").rstrip("/")


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
        logger.exception("auth: signup failed for %s", auth.mask_email(request.email))
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
        logger.exception("auth: login lookup failed for %s", auth.mask_email(request.email))
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


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(request: ForgotPasswordRequest):
    """
    Request a password reset email.

    Always returns the same generic message whether or not the email
    belongs to a real account — a different response would let an attacker
    enumerate registered emails. This means a successful HTTP response here
    does NOT confirm an email was actually sent; check server logs for that.
    """
    _require_db()
    try:
        user = db.get_user_by_email(request.email)
    except Exception:
        logger.exception("auth: forgot-password lookup failed for %s", auth.mask_email(request.email))
        # Still return the generic response -- a DB hiccup must not leak
        # "this email doesn't exist" information via an error response either.
        return ForgotPasswordResponse()

    if user is None:
        logger.info("auth: forgot-password requested for unknown email (no email sent).")
        return ForgotPasswordResponse()

    token = auth.generate_reset_token()
    token_hash = auth.hash_reset_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=auth.PASSWORD_RESET_EXPIRY_MINUTES)

    try:
        db.create_password_reset(user["id"], token_hash, expires_at)
    except Exception:
        logger.exception("auth: could not store password reset token for user %s", user["id"])
        return ForgotPasswordResponse()

    reset_link = f"{FRONTEND_BASE_URL}/?reset_token={token}"
    sent = email.send_password_reset_email(user["email"], reset_link)
    logger.info(
        "auth: password reset requested for user %s (email_sent=%s)", user["id"], sent,
    )
    return ForgotPasswordResponse()


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(request: ResetPasswordRequest):
    """
    Consume a password reset token and set a new password.

    A token is single-use and expires after
    auth.PASSWORD_RESET_EXPIRY_MINUTES (default 60 minutes).
    """
    _require_db()
    token_hash = auth.hash_reset_token(request.token)
    try:
        reset_row = db.get_password_reset_by_token_hash(token_hash)
    except Exception:
        logger.exception("auth: reset-password lookup failed.")
        raise HTTPException(status_code=503, detail="Could not reach the account database right now.")

    if reset_row is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid.")
    if reset_row["used_at"] is not None:
        raise HTTPException(status_code=400, detail="This reset link has already been used.")

    expires_at = reset_row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="This reset link has expired. Request a new one.")

    new_hash = auth.hash_password(request.new_password)
    try:
        db.update_user_password(reset_row["user_id"], new_hash)
        db.mark_password_reset_used(reset_row["id"])
    except Exception:
        logger.exception("auth: failed to apply password reset for user %s", reset_row["user_id"])
        raise HTTPException(status_code=503, detail="Could not update the password right now. Try again shortly.")

    logger.info("auth: password reset completed for user %s", reset_row["user_id"])
    return ResetPasswordResponse()
