import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _unique_email():
    from uuid import uuid4
    return f"resend_{uuid4().hex[:8]}@example.com"


def test_resend_verification_happy_path(monkeypatch):
    sent = {"count": 0, "last_body": None, "last_to": None}

    def fake_send(to, subject, body, settings=None):
        sent["count"] += 1
        sent["last_body"] = body
        sent["last_to"] = to

    import app.routers.auth as auth_router
    monkeypatch.setattr(auth_router, "send_email", fake_send, raising=False)

    email = _unique_email()
    # Register (creates unverified profile)
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Abcd!234",
            "gdpr_consent": True,
            "ai_ack": True,
        },
    )
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    assert sent["count"] == 1  # initial verification email

    # Resend
    rr = client.post(
        "/auth/resend-verification",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert rr.status_code == 200, rr.text
    assert rr.json().get("detail") == "Verification email sent"
    assert sent["count"] == 2
    assert sent["last_to"] == email
    assert sent["last_body"] and "/auth/verify-email?token=" in sent["last_body"]


def test_resend_verification_already_verified(monkeypatch):
    sent = {"count": 0}

    def fake_send(*args, **kwargs):
        sent["count"] += 1

    import app.routers.auth as auth_router
    monkeypatch.setattr(auth_router, "send_email", fake_send, raising=False)

    email = _unique_email()
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Abcd!234",
            "gdpr_consent": True,
            "ai_ack": True,
        },
    )
    assert r.status_code == 200
    access = r.json()["access_token"]

    # Mark profile verified directly via token call
    from app.settings import get_settings
    from app.utils.email_verification import create_email_verification_token
    token = create_email_verification_token(r.json()["user_id"], email, get_settings())
    vr = client.get(f"/auth/verify-email?token={token}")
    assert vr.status_code == 200

    rr = client.post(
        "/auth/resend-verification",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert rr.status_code == 400
    assert rr.json().get("detail") == "Email already verified"