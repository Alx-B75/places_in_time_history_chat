# tests/test_threads_errors.py
"""
Thread creation error-path tests.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_thread_without_auth_is_rejected() -> None:
    """Creating a thread without authentication should be rejected."""
    r = client.post("/threads", json={"user_id": 1, "title": "Nope"})
    assert r.status_code in (401, 403)
