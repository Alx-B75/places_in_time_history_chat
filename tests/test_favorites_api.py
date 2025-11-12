import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db_chat
from app.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_chat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure tables
Base.metadata.create_all(bind=engine)


def override_get_db_chat():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db_chat] = override_get_db_chat

client = TestClient(app)


def create_and_login_user(username: str = "favuser@example.com", password: str = "Admin!123"):
    # register via compatibility endpoint (simple payload)
    r = client.post("/register", json={"username": username, "password": password})
    assert r.status_code in (200, 400), r.text  # 400 if already exists
    # login via compatibility endpoint (simple JSON)
    r = client.post("/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return token


def test_favorites_add_list_remove_flow():
    token = create_and_login_user()

    # pick any existing figure slug via list
    fr = client.get("/figures")
    assert fr.status_code == 200
    figures = fr.json()
    assert figures, "Expected at least one figure for favorites test"
    slug = figures[0]["slug"]

    headers = {"Authorization": f"Bearer {token}"}

    # ensure empty favorites initially
    r = client.get("/user/favorites", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

    # add
    r = client.post(f"/user/favorites/{slug}", headers=headers)
    assert r.status_code in (200, 201)
    fav = r.json()
    assert fav["figure_slug"] == slug

    # list shows it
    r = client.get("/user/favorites", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert any(f["figure_slug"] == slug for f in data)

    # delete
    r = client.delete(f"/user/favorites/{slug}", headers=headers)
    assert r.status_code == 204

    # list empty again
    r = client.get("/user/favorites", headers=headers)
    assert r.status_code == 200
    assert all(f["figure_slug"] != slug for f in r.json())
