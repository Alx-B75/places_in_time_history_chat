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
    assert body.get("ok") is True

    assert body.get("chat_db_url")
    assert body.get("figures_db_url")

    keys_present = body.get("keys_present")
    assert isinstance(keys_present, dict)
    for key in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        assert key in keys_present
        assert isinstance(keys_present[key], bool)

    rag_status = body.get("rag")
    assert isinstance(rag_status, dict)
    for key in ("enabled", "ok", "detail"):
        assert key in rag_status

    debug_payload = body.get("debug")
    assert isinstance(debug_payload, dict)
