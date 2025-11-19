from fastapi.testclient import TestClient
from app.main import app
from app.config.llm_config import llm_config


def test_patch_admin_llm_updates_model(monkeypatch, admin_auth_header):
    llm_config.api_key = "dummy"
    client = TestClient(app)

    class DummyLLMClient:
        def generate(self, messages, temperature=0.0, max_tokens=5, **kwargs):
            return {"model": "patched-model", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setattr("app.services.llm_client.llm_client", DummyLLMClient())

    patch_payload = {
        "provider": "openai",
        "model": "patched-model"
    }
    resp = client.patch(
        "/admin/llm",
        json=patch_payload,
        headers=admin_auth_header,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"]["model"] == "patched-model"

    health_resp = client.get(
        "/admin/llm/health",
        headers=admin_auth_header,
    )
    assert health_resp.status_code == 200, health_resp.text
    assert health_resp.json()["model"] == "patched-model"
