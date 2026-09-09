"""
Account deletion: DELETE /auth/account.

services.db is mocked with an in-memory fake (same pattern as test_auth.py and
test_password_reset.py) so nothing here touches a real database.

This endpoint is irreversible and has no undo, so the tests below care as much
about what it REFUSES to do as about the happy path: no token, wrong password,
and — the one that would actually matter in production — that the user's stored
résumés, answers and reports are genuinely removed rather than merely detached
from the account. The real schema declares those tables ON DELETE SET NULL, so
an implementation that leaned on the foreign keys would pass a naive "user row
is gone" assertion while leaving every résumé sitting in the database.
"""

from __future__ import annotations

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
    from services import db

    users: dict = {}
    users_by_id: dict = {}
    # Child rows, keyed by table -> list of {user_id: ...}
    child_rows: dict = {"interactions": [], "resumes": [], "reports": [], "password_resets": []}
    next_user_id = [1]

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

    def fake_delete_user_account(user_id):
        counts = {}
        for table, rows in child_rows.items():
            before = len(rows)
            rows[:] = [r for r in rows if r["user_id"] != user_id]
            counts[table] = before - len(rows)
        u = users_by_id.pop(user_id, None)
        if u:
            users.pop(u["email"], None)
        counts["users"] = 1 if u else 0
        return counts

    monkeypatch.setattr(db, "is_enabled", fake_is_enabled)
    monkeypatch.setattr(db, "create_user", fake_create_user)
    monkeypatch.setattr(db, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(db, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(db, "delete_user_account", fake_delete_user_account)

    return {"users": users, "users_by_id": users_by_id, "child_rows": child_rows}


def _signup(client, email="del@example.com", password="correct-horse-1"):
    r = client.post("/auth/signup", json={"email": email, "password": password, "name": "Del"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_requires_authentication(client, fake_db):
    r = client.request("DELETE", "/auth/account", json={"password": "whatever"})
    assert r.status_code == 401


def test_rejects_wrong_password_and_keeps_the_account(client, fake_db):
    token = _signup(client)
    r = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "not-the-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
    assert "Incorrect password" in r.json()["detail"]
    # The account must still be there -- a failed confirmation cannot be
    # allowed to partially delete anything.
    assert fake_db["users_by_id"].get(1) is not None


def test_deletes_the_account_and_all_child_rows(client, fake_db):
    token = _signup(client)

    # Give the user data in every table that stores something about them.
    for table in ("interactions", "resumes", "reports", "password_resets"):
        fake_db["child_rows"][table].append({"user_id": 1})
        fake_db["child_rows"][table].append({"user_id": 999})  # another user's row

    r = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "correct-horse-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "permanently deleted" in body["message"]

    # The user is gone.
    assert fake_db["users_by_id"] == {}
    assert body["deleted"]["users"] == 1

    # Their stored data is genuinely gone, not merely orphaned...
    for table in ("interactions", "resumes", "reports", "password_resets"):
        remaining = fake_db["child_rows"][table]
        assert all(row["user_id"] != 1 for row in remaining), f"{table} kept the deleted user's rows"
        assert body["deleted"][table] == 1
        # ...and nobody else's data was caught in the blast radius.
        assert any(row["user_id"] == 999 for row in remaining), f"{table} deleted another user's rows"


def test_token_stops_working_after_deletion(client, fake_db):
    token = _signup(client)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/auth/me", headers=headers).status_code == 200

    r = client.request("DELETE", "/auth/account", json={"password": "correct-horse-1"}, headers=headers)
    assert r.status_code == 200

    # The JWT is still cryptographically valid until it expires -- it is
    # stateless. What must not happen is it continuing to resolve to a user.
    assert client.get("/auth/me", headers=headers).status_code == 404


def test_returns_503_when_storage_is_not_configured(client, monkeypatch):
    from services import db

    token = auth_service.create_access_token(user_id=1, email="x@example.com")
    monkeypatch.setattr(db, "is_enabled", lambda: False)
    r = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "irrelevant"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503
