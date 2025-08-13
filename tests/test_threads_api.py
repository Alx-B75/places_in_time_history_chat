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
    user_id = reg.json()["user_id"]

    r = client.post("/threads", json={"user_id": user_id, "title": "T1"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert {"thread_id", "user_id", "title"} <= set(data.keys())
    assert data["user_id"] == user_id
    assert data["title"] == "T1"
