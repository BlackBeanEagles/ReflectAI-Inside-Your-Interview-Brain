"""
Email module.
Responsibility: Send transactional emails (currently just password reset)
via Resend's HTTP API.

Design notes:
    - Best-effort like most of this codebase's external-service calls:
      never raises. A failed send is logged and returns False so the caller
      can decide what to tell the user, but a broken email provider must
      never crash the request.
    - Resend's sandbox sender (the default RESEND_FROM_EMAIL below,
      onboarding@resend.dev) only delivers to the email address associated
      with the Resend account itself until a custom sending domain is
      verified in the Resend dashboard. Until that's done, real password
      reset emails to arbitrary users will not actually arrive — this is a
      known, documented limitation of the free/unverified tier, not a bug
      in this code. See README "Known limitations".
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()
RESEND_API_URL = "https://api.resend.com/emails"


def is_available() -> bool:
    return bool(RESEND_API_KEY)


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Send a password reset email via Resend.

    Returns True only on a confirmed successful send. Never raises — every
    failure (missing API key, network error, Resend rejecting the request)
    is logged and returns False.
    """
    if not RESEND_API_KEY:
        logger.warning("email: RESEND_API_KEY is not set — cannot send password reset email.")
        return False

    subject = "Reset your ReflectInterview password"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Reset your password</h2>
        <p>Someone requested a password reset for this email's ReflectInterview account.
        If this wasn't you, you can safely ignore this email.</p>
        <p><a href="{reset_link}" style="display:inline-block; background:#4f6ef7; color:#fff;
           padding:0.6rem 1.2rem; border-radius:6px; text-decoration:none;">Reset Password</a></p>
        <p>Or paste this link into your browser:<br>{reset_link}</p>
        <p style="color:#888; font-size:0.85em;">This link expires in 1 hour and can only be used once.</p>
    </div>
    """

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"ReflectInterview <{RESEND_FROM_EMAIL}>",
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            logger.error(
                "email: Resend rejected the send (status=%d): %s",
                response.status_code, response.text[:300],
            )
            return False
        logger.info("email: password reset email sent to %s", to_email)
        return True
    except requests.exceptions.Timeout:
        logger.error("email: Resend request timed out.")
        return False
    except Exception:
        logger.exception("email: unexpected failure sending password reset email.")
        return False
