"""
Health endpoint test for the FastAPI application.
"""
from fastapi.testclient import TestClient
from app.main import app


def test_health_ok() -> None:
    """
    Calls the health endpoint and asserts a 200 response with a JSON body.
    """
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, dict)
    assert body != {}
