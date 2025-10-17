import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_admin_llm_health(monkeypatch):
    class DummyResp(dict):
        def __init__(self):
            super().__init__(model="gpt-4", usage={"prompt_tokens": 1, "completion_tokens": 1})
            self.model = "gpt-4"
            self.usage = {"prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr("openai.ChatCompletion.create", lambda *a, **kw: DummyResp())
    client = TestClient(app)
    resp = client.get("/admin/health/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "model" in data
