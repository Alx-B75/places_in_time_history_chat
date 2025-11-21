from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_admin_list_users_includes_email_and_verified(admin_auth_header, db_session):
    # Ensure at least one user with profile exists
    from app import models
    u = db_session.query(models.User).filter(models.User.username == "contact_user").first()
    if not u:
        u = models.User(username="contact_user", hashed_password="x", role="user")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    prof = db_session.query(models.UserProfile).filter(models.UserProfile.user_id == u.id).first()
    if prof is None:
        prof = models.UserProfile(user_id=u.id, email="contact_user@example.com", email_verified=1)
        db_session.add(prof)
        db_session.commit()

    r = client.get("/admin/users", headers=admin_auth_header)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    target = next((row for row in arr if row["username"] == "contact_user"), None)
    assert target is not None
    assert target.get("email") == "contact_user@example.com"
    assert target.get("email_verified") is True


def test_admin_email_user_sends_email(monkeypatch, admin_auth_header, db_session):
    sent = {}

    def fake_send(to, subject, body, settings=None):
        sent["to"] = to
        sent["subject"] = subject
        sent["body"] = body

    import app.routers.admin as admin_router
    import app.utils.email_utils as email_utils
    monkeypatch.setattr(email_utils, "send_email", fake_send, raising=False)
    monkeypatch.setattr(admin_router, "send_email", fake_send, raising=False)

    from app import models
    u = db_session.query(models.User).filter(models.User.username == "email_target").first()
    if not u:
        u = models.User(username="email_target", hashed_password="x", role="user")
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    prof = db_session.query(models.UserProfile).filter(models.UserProfile.user_id == u.id).first()
    if prof is None:
        prof = models.UserProfile(user_id=u.id, email="email_target@example.com", email_verified=1)
        db_session.add(prof)
        db_session.commit()

    r = client.post(f"/admin/users/{u.id}/email", json={"subject": "Hello", "body": "Test"}, headers=admin_auth_header)
    assert r.status_code == 200, r.text
    assert sent.get("to") == "email_target@example.com"
