import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings

client = TestClient(app)


def test_register_requires_email_schema():
    # Missing email should be a validation error (422)
    r = client.post("/auth/register", json={"password": "Abcd!234", "gdpr_consent": True, "ai_ack": True})
    assert r.status_code in (400, 422)


def test_register_with_email_creates_profile_and_sends_email(monkeypatch):
    sent = {}

    def fake_send(to, subject, body, settings=None):
        sent["to"] = to
        sent["subject"] = subject
        sent["body"] = body

    import app.routers.auth as auth_router
    import app.utils.email_utils as email_utils
    monkeypatch.setattr(auth_router, "send_email", fake_send, raising=False)
    monkeypatch.setattr(email_utils, "send_email", fake_send, raising=False)

    payload = {
        # Use unique email to avoid collisions between test runs
        "email": f"newuser_{__import__('uuid').uuid4().hex[:8]}@example.com",
        "password": "Abcd!234",
        "gdpr_consent": True,
        "ai_ack": True,
    }
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("email_verification_sent") is True
    # New: ensure verification_url is absolute and contains token
    verify_url = data.get("verification_url")
    token = data.get("verification_token")
    assert verify_url and verify_url.startswith("http")
    if token:
        assert f"/auth/verify-email?token={token}" in verify_url
    # token may be included for dev; not strictly required
    # ensure our fake sender captured call
    assert sent.get("to") == payload["email"]


def test_verify_email_marks_profile_verified(db_session):
    # Create user via legacy register to get a user; then set up profile unverified
    r = client.post("/register", json={"username": "verify_me", "password": "pw"})
    assert r.status_code == 200
    user_id = r.json()["user_id"]

    from app import models
    # Use a unique email per test run to avoid UNIQUE constraint collisions
    from uuid import uuid4
    unique_email = f"verify_{uuid4().hex[:8]}@example.com"
    prof = db_session.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    if prof is None:
        prof = models.UserProfile(user_id=user_id, email=unique_email, email_verified=0)
        db_session.add(prof)
    else:
        prof.email = unique_email
        prof.email_verified = 0
    db_session.commit()

    # Create token and verify
    from app.utils.email_verification import create_email_verification_token
    token = create_email_verification_token(user_id, unique_email, get_settings())
    vr = client.get(f"/auth/verify-email?token={token}")
    assert vr.status_code == 200, vr.text
    prof2 = db_session.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    assert prof2 and int(getattr(prof2, "email_verified", 0)) == 1
