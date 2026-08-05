"""
Auth tests: password hashing/JWT unit tests (no DB), plus the signup/login/
me/history HTTP flow with services.db mocked (no real Postgres needed, same
pattern conftest.py uses to stub the LLM).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from services import auth as auth_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── Pure unit tests: hashing + JWT, no DB, no HTTP ────────────────────────────

def test_password_hash_and_verify_round_trip():
    h = auth_service.hash_password("correct horse battery staple")
    assert auth_service.verify_password("correct horse battery staple", h)
    assert not auth_service.verify_password("wrong password", h)


def test_password_hash_never_stores_plaintext():
    h = auth_service.hash_password("mypassword123")
    assert "mypassword123" not in h


def test_token_round_trip():
    token = auth_service.create_access_token(7, "a@b.com")
    claims = auth_service.decode_access_token(token)
    assert claims == {"user_id": 7, "email": "a@b.com"}


def test_invalid_token_returns_none():
    assert auth_service.decode_access_token("not.a.valid.token") is None
    assert auth_service.decode_access_token("") is None


def test_tampered_token_is_rejected():
    token = auth_service.create_access_token(7, "a@b.com")
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    assert auth_service.decode_access_token(tampered) is None


# ── HTTP flow: DB not configured ──────────────────────────────────────────────

def test_signup_returns_503_when_db_not_configured(client, monkeypatch):
    from services import db
    monkeypatch.setattr(db, "DATABASE_URL", "")
    r = client.post("/auth/signup", json={"email": "a@b.com", "password": "password123"})
    assert r.status_code == 503


def test_login_returns_503_when_db_not_configured(client, monkeypatch):
    from services import db
    monkeypatch.setattr(db, "DATABASE_URL", "")
    r = client.post("/auth/login", json={"email": "a@b.com", "password": "password123"})
    assert r.status_code == 503


# ── HTTP flow: DB mocked as available ────────────────────────────────────────

@pytest.fixture
def fake_db(monkeypatch):
    """A tiny in-memory fake standing in for services.db, keyed by email."""
    from services import db

    store = {}
    next_id = [1]

    def fake_is_enabled():
        return True

    def fake_create_user(email, password_hash, name=None):
        if email in store:
            return None
        user = {"id": next_id[0], "email": email, "password_hash": password_hash, "name": name}
        store[email] = user
        next_id[0] += 1
        return {"id": user["id"], "email": user["email"], "name": user["name"]}

    def fake_get_user_by_email(email):
        return store.get(email)

    def fake_get_user_by_id(user_id):
        for u in store.values():
            if u["id"] == user_id:
                return {"id": u["id"], "email": u["email"], "name": u["name"]}
        return None

    def fake_get_user_reports(user_id, limit=20):
        return []

    monkeypatch.setattr(db, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(db, "create_user", fake_create_user)
    monkeypatch.setattr(db, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(db, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(db, "get_user_reports", fake_get_user_reports)
    return store


def test_signup_creates_user_and_returns_token(client, fake_db):
    r = client.post("/auth/signup", json={"email": "jane@example.com", "password": "password123", "name": "Jane"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "jane@example.com"
    assert body["token_type"] == "bearer"
    assert auth_service.decode_access_token(body["access_token"])["email"] == "jane@example.com"


def test_signup_duplicate_email_returns_409(client, fake_db):
    client.post("/auth/signup", json={"email": "dupe@example.com", "password": "password123"})
    r = client.post("/auth/signup", json={"email": "dupe@example.com", "password": "differentpass"})
    assert r.status_code == 409


def test_signup_rejects_short_password(client, fake_db):
    r = client.post("/auth/signup", json={"email": "short@example.com", "password": "abc"})
    assert r.status_code == 422


def test_signup_rejects_invalid_email(client, fake_db):
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "password123"})
    assert r.status_code == 422


def test_login_success(client, fake_db):
    client.post("/auth/signup", json={"email": "login@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "login@example.com", "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password_returns_401(client, fake_db):
    client.post("/auth/signup", json={"email": "login2@example.com", "password": "password123"})
    r = client.post("/auth/login", json={"email": "login2@example.com", "password": "wrongpassword"})
    assert r.status_code == 401


def test_login_unknown_email_returns_401_not_404(client, fake_db):
    """Same error for unknown email as wrong password — don't leak which one is wrong."""
    r = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert r.status_code == 401


def test_me_requires_auth_header(client, fake_db):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_rejects_invalid_token(client, fake_db):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_me_returns_current_user_with_valid_token(client, fake_db):
    signup = client.post("/auth/signup", json={"email": "whoami@example.com", "password": "password123"})
    token = signup.json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "whoami@example.com"


def test_history_requires_auth(client, fake_db):
    r = client.get("/auth/history")
    assert r.status_code == 401


def test_history_returns_empty_list_for_new_user(client, fake_db):
    signup = client.post("/auth/signup", json={"email": "hist@example.com", "password": "password123"})
    token = signup.json()["access_token"]
    r = client.get("/auth/history", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["reports"] == []


def test_session_start_works_without_auth_exactly_as_before(client):
    """Anonymous use must keep working unchanged — login is optional everywhere."""
    r = client.post("/session/start")
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_session_start_with_valid_token_links_user(client, fake_db):
    from services import session_manager
    signup = client.post("/auth/signup", json={"email": "sessionlink@example.com", "password": "password123"})
    token = signup.json()["access_token"]
    user_id = signup.json()["user"]["id"]

    r = client.post("/session/start", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert session_manager.get_session_user_id(sid) == user_id


def test_session_start_with_bad_token_falls_back_to_anonymous(client):
    """An invalid token shouldn't break session creation — just treated as anonymous."""
    r = client.post("/session/start", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 200
