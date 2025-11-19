from typing import Dict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db_chat
from app.utils.security import create_access_token


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_chat.db"
test_engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Ensure tables exist for tests
Base.metadata.create_all(bind=test_engine)


def override_get_db_chat():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply override once for all tests before any TestClient(app) is created.
from app.main import app

app.dependency_overrides[get_db_chat] = override_get_db_chat


@pytest.fixture
def db_session():
    """Yield a test DB session backed by TestingSessionLocal."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_or_create_test_admin(db) -> models.User:
    admin = (
        db.query(models.User)
        .filter(models.User.username == "test_admin")
        .first()
    )
    if admin is None:
        admin = models.User(
            username="test_admin",
            hashed_password="dummy",  # not used in these tests
            role="admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return admin


@pytest.fixture
def admin_auth_header(db_session) -> Dict[str, str]:
    """Return an Authorization header for a seeded admin user.

    Uses the shared test DB session so all tests see the same admin.
    """
    admin = _get_or_create_test_admin(db_session)
    token = create_access_token({"sub": admin.username}, scope="admin")
    return {"Authorization": f"Bearer {token}"}
