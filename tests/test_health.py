"""
Health endpoint test for the FastAPI application.
"""
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_public_is_minimal() -> None:
    """Public /health should expose only minimal, non-sensitive fields."""
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == {"status", "environment", "rag_enabled", "chat_db_ok", "figures_db_ok"}
    # Ensure potentially sensitive substructures are not present
    assert "keys" not in body
    assert "rag" not in body
    assert "guest_prompt_debug" not in body


def test_health_admin_requires_auth() -> None:
    res = client.get("/health/admin")
    assert res.status_code in (401, 403)


def test_health_admin_allows_admin(admin_auth_header) -> None:
    res = client.get("/health/admin", headers=admin_auth_header)
    assert res.status_code == 200
    body = res.json()
    # Admin health should include detailed structures
    assert "keys" in body
    assert "rag" in body
    assert "guest_prompt_debug" in body
