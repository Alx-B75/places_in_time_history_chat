import os
from fastapi.testclient import TestClient
from app.main import app
from app.config.llm_config import llm_config

def test_admin_llm_health(monkeypatch):
    # Force dev environment bypass for admin_required
    monkeypatch.setenv("ENVIRONMENT", "dev")

    class DummyLLMClient:
        def generate(self, messages, temperature=0.0, max_tokens=5, **kwargs):
            return {"model": "gpt-4", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    # Patch llm_client used inside admin router
    monkeypatch.setattr("app.services.llm_client.llm_client", DummyLLMClient())

    # Set a dummy API key to avoid runtime errors inside LlmClient
    llm_config.api_key = "dummy"
    client = TestClient(app)
    resp = client.get("/admin/health/llm")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "provider" in data
    assert "model" in data
