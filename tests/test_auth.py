import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def new_user():
    return {"username": "testuser_auth", "password": "securepass123"}


def test_register_and_login(new_user):
    # --- Register ---
    r = client.post("/register", json=new_user)
    assert r.status_code == 200, f"Register failed: {r.json()}"
    data = r.json()
    assert "access_token" in data
    assert data["username"] == new_user["username"]

    # --- Login ---
    r = client.post("/login", json=new_user)
    assert r.status_code == 200, f"Login failed: {r.json()}"
    data = r.json()
    assert "access_token" in data
    assert data["username"] == new_user["username"]
