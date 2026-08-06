"""
Password reset flow: POST /auth/forgot-password and POST /auth/reset-password.

services.db is mocked with an in-memory fake (same pattern as test_auth.py's
fake_db fixture) and services.email.send_password_reset_email is stubbed to
avoid any real network call to Resend.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from services import auth as auth_service


@pytest.fixture
def client() -> TestClient:
    import app.main as main_module
    main_module._request_log.clear()
    return TestClient(app)


@pytest.fixture
def fake_db(monkeypatch):
    """In-memory fake standing in for services.db, covering users + password_resets."""
    from services import db

    users = {}          # email -> user dict (includes password_hash)
    users_by_id = {}     # id -> user dict
    resets = {}          # id -> {id, user_id, token_hash, expires_at, used_at}
    next_user_id = [1]
    next_reset_id = [1]

    def fake_is_enabled():
        return True

    def fake_create_user(email, password_hash, name=None):
        if email in users:
            return None
        user = {"id": next_user_id[0], "email": email, "password_hash": password_hash, "name": name}
        users[email] = user
        users_by_id[user["id"]] = user
        next_user_id[0] += 1
        return {"id": user["id"], "email": user["email"], "name": user["name"]}

    def fake_get_user_by_email(email):
        return users.get(email)

    def fake_get_user_by_id(user_id):
        u = users_by_id.get(user_id)
        if not u:
            return None
        return {"id": u["id"], "email": u["email"], "name": u["name"]}

    def fake_create_password_reset(user_id, token_hash, expires_at):
        reset = {
            "id": next_reset_id[0], "user_id": user_id,
            "token_hash": token_hash, "expires_at": expires_at, "used_at": None,
        }
        resets[reset["id"]] = reset
        next_reset_id[0] += 1

    def fake_get_password_reset_by_token_hash(token_hash):
        matches = [r for r in resets.values() if r["token_hash"] == token_hash]
        if not matches:
            return None
        return dict(matches[-1])

    def fake_mark_password_reset_used(reset_id):
        resets[reset_id]["used_at"] = datetime.now(timezone.utc)

    def fake_update_user_password(user_id, password_hash):
        users_by_id[user_id]["password_hash"] = password_hash

    monkeypatch.setattr(db, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(db, "create_user", fake_create_user)
    monkeypatch.setattr(db, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(db, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(db, "create_password_reset", fake_create_password_reset)
    monkeypatch.setattr(db, "get_password_reset_by_token_hash", fake_get_password_reset_by_token_hash)
    monkeypatch.setattr(db, "mark_password_reset_used", fake_mark_password_reset_used)
    monkeypatch.setattr(db, "update_user_password", fake_update_user_password)
    return users


@pytest.fixture
def fake_email_sent(monkeypatch):
    """Stub the actual email send and capture what would have been sent."""
    import api.routes.auth as auth_route

    sent = []

    def fake_send(to_email, reset_link):
        sent.append({"to": to_email, "link": reset_link})
        return True

    monkeypatch.setattr(auth_route.email, "send_password_reset_email", fake_send)
    return sent


# ── /auth/forgot-password ────────────────────────────────────────────────────

def test_forgot_password_unknown_email_returns_generic_message(client, fake_db, fake_email_sent):
    r = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "password reset link has been sent" in r.json()["message"].lower()
    assert fake_email_sent == []  # nothing actually sent for an unknown email


def test_forgot_password_known_email_sends_email_and_generic_message(client, fake_db, fake_email_sent):
    client.post("/auth/signup", json={"email": "real@example.com", "password": "password123"})
    r = client.post("/auth/forgot-password", json={"email": "real@example.com"})
    assert r.status_code == 200
    assert "password reset link has been sent" in r.json()["message"].lower()
    assert len(fake_email_sent) == 1
    assert fake_email_sent[0]["to"] == "real@example.com"
    assert "reset_token=" in fake_email_sent[0]["link"]


def test_forgot_password_response_identical_for_known_and_unknown_email(client, fake_db, fake_email_sent):
    """The whole point of the generic response -- an attacker probing emails
    must not be able to tell which ones are registered."""
    client.post("/auth/signup", json={"email": "known@example.com", "password": "password123"})
    r1 = client.post("/auth/forgot-password", json={"email": "known@example.com"})
    r2 = client.post("/auth/forgot-password", json={"email": "unknown@example.com"})
    assert r1.json() == r2.json()
    assert r1.status_code == r2.status_code == 200


def test_forgot_password_rejects_invalid_email_format(client, fake_db, fake_email_sent):
    r = client.post("/auth/forgot-password", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_forgot_password_requires_db(client, monkeypatch):
    from services import db
    monkeypatch.setattr(db, "DATABASE_URL", "")
    r = client.post("/auth/forgot-password", json={"email": "a@b.com"})
    assert r.status_code == 503


# ── /auth/reset-password ─────────────────────────────────────────────────────

def _request_reset_and_get_token(client, fake_email_sent, email="real@example.com"):
    client.post("/auth/forgot-password", json={"email": email})
    link = fake_email_sent[-1]["link"]
    return link.split("reset_token=")[1]


def test_reset_password_success(client, fake_db, fake_email_sent):
    client.post("/auth/signup", json={"email": "real@example.com", "password": "oldpassword123"})
    token = _request_reset_and_get_token(client, fake_email_sent)

    r = client.post("/auth/reset-password", json={"token": token, "new_password": "newpassword456"})
    assert r.status_code == 200

    # Old password no longer works, new one does.
    old_login = client.post("/auth/login", json={"email": "real@example.com", "password": "oldpassword123"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", json={"email": "real@example.com", "password": "newpassword456"})
    assert new_login.status_code == 200


def test_reset_password_token_is_single_use(client, fake_db, fake_email_sent):
    client.post("/auth/signup", json={"email": "real@example.com", "password": "oldpassword123"})
    token = _request_reset_and_get_token(client, fake_email_sent)

    r1 = client.post("/auth/reset-password", json={"token": token, "new_password": "firstnewpass"})
    assert r1.status_code == 200

    r2 = client.post("/auth/reset-password", json={"token": token, "new_password": "secondnewpass"})
    assert r2.status_code == 400
    assert "already been used" in r2.json()["detail"].lower()


def test_reset_password_rejects_unknown_token(client, fake_db):
    r = client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "newpassword123"})
    assert r.status_code == 400
    assert "invalid" in r.json()["detail"].lower()


def test_reset_password_rejects_expired_token(client, fake_db, fake_email_sent, monkeypatch):
    from services import db

    client.post("/auth/signup", json={"email": "real@example.com", "password": "oldpassword123"})

    # Force the stored expiry into the past regardless of the configured window.
    original_create = db.create_password_reset

    def expired_create(user_id, token_hash, expires_at):
        original_create(user_id, token_hash, datetime.now(timezone.utc) - timedelta(minutes=5))

    monkeypatch.setattr(db, "create_password_reset", expired_create)
    token = _request_reset_and_get_token(client, fake_email_sent)

    r = client.post("/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


def test_reset_password_rejects_short_new_password(client, fake_db, fake_email_sent):
    client.post("/auth/signup", json={"email": "real@example.com", "password": "oldpassword123"})
    token = _request_reset_and_get_token(client, fake_email_sent)
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "short"})
    assert r.status_code == 422


def test_reset_password_requires_db(client, monkeypatch):
    from services import db
    monkeypatch.setattr(db, "DATABASE_URL", "")
    r = client.post("/auth/reset-password", json={"token": "abc", "new_password": "newpassword123"})
    assert r.status_code == 503


# ── auth.py token helpers (pure unit tests) ──────────────────────────────────

def test_generate_reset_token_is_random_and_url_safe():
    t1 = auth_service.generate_reset_token()
    t2 = auth_service.generate_reset_token()
    assert t1 != t2
    assert len(t1) > 20


def test_hash_reset_token_is_deterministic_and_one_way():
    token = "some-random-token-value"
    h1 = auth_service.hash_reset_token(token)
    h2 = auth_service.hash_reset_token(token)
    assert h1 == h2
    assert token not in h1
