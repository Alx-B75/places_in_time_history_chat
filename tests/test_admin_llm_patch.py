from fastapi.testclient import TestClient
from app.main import app

def test_patch_admin_llm_updates_model(monkeypatch):
    client = TestClient(app)

    class DummyLLMClient:
        def generate(self, messages, temperature=0.0, max_tokens=5, **kwargs):
            return {"model": "patched-model", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setattr("app.services.llm_client.llm_client", DummyLLMClient())

    token = "Bearer test-admin-token"
    patch_payload = {
        "provider": "openai",
        "model": "patched-model"
    }
    resp = client.patch(
        "/admin/llm",
        json=patch_payload,
        headers={"Authorization": token}
    )
    assert resp.status_code == 200
    assert resp.json()["active"]["model"] == "patched-model"

    health_resp = client.get(
        "/admin/llm/health",
        headers={"Authorization": token}
    )
    assert health_resp.status_code == 200
    assert health_resp.json()["model"] == "patched-model"
