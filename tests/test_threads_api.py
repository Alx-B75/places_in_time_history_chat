"""
Thread creation API test with unique user to avoid collisions across runs.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_thread_returns_identity() -> None:
    """
    Registers a unique user, creates a thread, and asserts identity fields are returned.
    """
    username = f"threads_user_{uuid4().hex[:8]}"
    reg = client.post("/register", json={"username": username, "password": "pw"})
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    user_id = reg.json()["user_id"]

    # user_id field is optional; if omitted, backend should still
    # associate the thread with the authenticated user.
    r = client.post(
        "/threads",
        json={"title": "T1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert {"thread_id", "user_id", "title"} <= set(data.keys())
    assert data["user_id"] == user_id
    assert data["title"] == "T1"


def test_create_thread_cannot_spoof_other_user() -> None:
    """Authenticated user cannot create a thread for a different user_id."""
    # Register two users
    reg_a = client.post("/register", json={"username": f"user_a", "password": "pw"})
    assert reg_a.status_code == 200, reg_a.text
    token_a = reg_a.json()["access_token"]

    reg_b = client.post("/register", json={"username": f"user_b", "password": "pw"})
    assert reg_b.status_code == 200, reg_b.text
    user_b_id = reg_b.json()["user_id"]

    # User A tries to create a thread for user B
    r = client.post(
        "/threads",
        json={"user_id": user_b_id, "title": "Spoofed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 403


def test_delete_thread_requires_owner_and_succeeds() -> None:
    """Register user, create a thread, then delete it with auth and verify 204 and 404 after."""
    username = f"del_user_{uuid4().hex[:8]}"
    reg = client.post("/register", json={"username": username, "password": "pw"})
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    user_id = reg.json()["user_id"]

    r = client.post(
        "/threads",
        json={"title": "ToDelete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    thread_id = r.json()["thread_id"]

    # Delete with proper auth
    delr = client.delete(f"/threads/{thread_id}", headers={"Authorization": f"Bearer {token}"})
    assert delr.status_code == 204, delr.text

    # Fetch should now be 404
    getr = client.get(f"/threads/{thread_id}", headers={"Authorization": f"Bearer {token}"})
    assert getr.status_code == 404


def test_delete_thread_forbidden_for_other_user() -> None:
    """A different user shouldn't be able to delete another user's thread."""
    # Owner
    owner = client.post("/register", json={"username": f"owner_{uuid4().hex[:8]}", "password": "pw"})
    assert owner.status_code == 200
    owner_token = owner.json()["access_token"]
    owner_id = owner.json()["user_id"]
    # Create thread for owner
    r = client.post(
        "/threads",
        json={"title": "OwnerThread"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r.status_code == 201
    thread_id = r.json()["thread_id"]

    # Attacker user
    attacker = client.post("/register", json={"username": f"att_{uuid4().hex[:8]}", "password": "pw"})
    assert attacker.status_code == 200
    attacker_token = attacker.json()["access_token"]

    # Attempt delete should be 403
    delr = client.delete(f"/threads/{thread_id}", headers={"Authorization": f"Bearer {attacker_token}"})
    assert delr.status_code == 403


def test_threads_list_includes_first_user_message_preview() -> None:
    """Create a thread with one user message and ensure preview fields are populated."""
    username = f"preview_{uuid4().hex[:8]}"
    reg = client.post("/register", json={"username": username, "password": "pw"})
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    user_id = reg.json()["user_id"]

    # Create a thread via API
    r = client.post(
        "/threads",
        json={"title": "HasPreview"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    thread_id = r.json()["thread_id"]

    # Post a user message via ask (no external LLM dependency needed for preview presence)
    askr = client.post(
        "/ask",
        json={"user_id": user_id, "message": "What can you tell me about Roman trade routes?", "thread_id": thread_id, "skip_llm": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert askr.status_code == 200, askr.text

    # List threads and verify preview
    list_r = client.get(f"/threads/user/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert list_r.status_code == 200
    arr = list_r.json()
    target = next((t for t in arr if t["id"] == thread_id), None)
    assert target is not None
    assert target.get("first_user_message")
    assert "Roman trade routes" in target.get("first_user_message")
    assert target.get("first_message_at")
