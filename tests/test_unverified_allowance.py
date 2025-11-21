from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _ensure_figure(slug: str = "a-druid"):
    # The seed/ingest may already include figures; just rely on existing slug used in UI/tests.
    return slug


def test_unverified_allowance_on_upgraded_thread(db_session):
    slug = _ensure_figure()

    # Register via /auth/register (creates profile with email_verified=False)
    from uuid import uuid4
    email = f"allowance_{uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "Abcd!234", "gdpr_consent": True, "ai_ack": True}
    reg = client.post("/auth/register", json=payload)
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user_id"]
    token = reg.json()["access_token"]

    # Start guest session and ask one to ensure session exists
    gs = client.post(f"/guest/start/{slug}")
    assert gs.status_code == 200, gs.text

    # Upgrade session to real thread (TestClient may drop Secure cookie; fetch token manually)
    from app import models
    session_row = db_session.query(models.GuestSession).order_by(models.GuestSession.id.desc()).first()
    assert session_row is not None
    guest_token = session_row.session_token
    up = client.post("/guest/upgrade", headers={"Authorization": f"Bearer {token}"}, cookies={"guest_session": guest_token})
    assert up.status_code == 200, up.text
    thread_id = up.json()["thread_id"]

    # Confirm meta exists with allowance 5
    from app import models
    meta = db_session.query(models.ThreadMeta).filter(models.ThreadMeta.thread_id == thread_id).first()
    assert meta is not None
    assert int(getattr(meta, "unverified_allowance_remaining", 0)) == 5

    # Ask 5 times; each should succeed and decrement
    for i in range(5):
        r = client.post(
            "/ask",
            json={"user_id": user_id, "message": f"Q{i}", "thread_id": thread_id, "skip_llm": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("email_verification_required") in (True, False)
    db_session.refresh(meta)
    assert int(getattr(meta, "unverified_allowance_remaining", 0)) == 0

    # Sixth ask should be blocked
    r6 = client.post(
        "/ask",
        json={"user_id": user_id, "message": "Q6", "thread_id": thread_id, "skip_llm": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r6.status_code == 403

    # Simulate verification and then asking again should pass
    prof = db_session.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    prof.email_verified = 1
    db_session.add(prof)
    db_session.commit()

    r7 = client.post(
        "/ask",
        json={"user_id": user_id, "message": "Q7", "thread_id": thread_id, "skip_llm": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r7.status_code == 200, r7.text
