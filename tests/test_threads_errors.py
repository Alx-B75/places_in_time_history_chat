# tests/test_threads_errors.py
"""
Thread creation error-path tests.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_thread_unknown_user_404() -> None:
    """
    Creating a thread for a non-existent user should return 404.
    """
    r = client.post("/threads", json={"user_id": 999999, "title": "Nope"})
    assert r.status_code == 404
    body = r.json()
    assert body.get("detail") == "User not found"
