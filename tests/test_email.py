"""Unit tests for services/email.py — Resend transactional email (mocked, no network)."""

import services.email as email


def test_unavailable_when_no_api_key(monkeypatch):
    monkeypatch.setattr(email, "RESEND_API_KEY", "")
    assert not email.is_available()
    result = email.send_password_reset_email("user@example.com", "https://example.com/reset?token=abc")
    assert result is False


def test_is_available_true_when_key_set(monkeypatch):
    monkeypatch.setattr(email, "RESEND_API_KEY", "re_fake_key")
    assert email.is_available()


def test_successful_send(monkeypatch):
    monkeypatch.setattr(email, "RESEND_API_KEY", "re_fake_key")

    class FakeResponse:
        status_code = 200
        text = '{"id": "abc123"}'

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(email.requests, "post", fake_post)
    result = email.send_password_reset_email("user@example.com", "https://example.com/reset?token=abc")
    assert result is True
    assert captured["url"] == email.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer re_fake_key"
    assert captured["json"]["to"] == ["user@example.com"]
    assert "reset?token=abc" in captured["json"]["html"]


def test_resend_rejection_returns_false(monkeypatch):
    monkeypatch.setattr(email, "RESEND_API_KEY", "re_fake_key")

    class FakeResponse:
        status_code = 422
        text = '{"message": "invalid from address"}'

    monkeypatch.setattr(email.requests, "post", lambda *a, **kw: FakeResponse())
    result = email.send_password_reset_email("user@example.com", "https://example.com/reset?token=abc")
    assert result is False


def test_timeout_returns_false(monkeypatch):
    monkeypatch.setattr(email, "RESEND_API_KEY", "re_fake_key")

    def fake_post(*a, **kw):
        import requests
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(email.requests, "post", fake_post)
    result = email.send_password_reset_email("user@example.com", "https://example.com/reset?token=abc")
    assert result is False


def test_unexpected_exception_never_raises(monkeypatch):
    monkeypatch.setattr(email, "RESEND_API_KEY", "re_fake_key")

    def fake_post(*a, **kw):
        raise RuntimeError("network is on fire")

    monkeypatch.setattr(email.requests, "post", fake_post)
    result = email.send_password_reset_email("user@example.com", "https://example.com/reset?token=abc")  # must not raise
    assert result is False
