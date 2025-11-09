"""
Ask endpoint happy-path test.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ask_returns_answer_and_persists() -> None:
    """
    Registers a user, creates a thread, posts a question to /ask, and
    asserts the response contract is satisfied.
    """
    reg = client.post("/register", json={"username": "ask_user_ok", "password": "pw"})
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user_id"]
    access_token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    t = client.post("/threads", json={"user_id": user_id, "title": "Ask Thread"})
    assert t.status_code == 201, t.text
    thread_id = t.json()["thread_id"]

    def fake_generate_answer(context, prompt, *, model="gpt-4o-mini", temperature=0.3):
        return "Hello from test", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    import app.routers.ask as ask_module
    original = ask_module.generate_answer
    ask_module.generate_answer = fake_generate_answer
    try:
        payload = {
            "user_id": user_id,
            "thread_id": thread_id,
            "figure_slug": "alexander-the-great",
            "message": "Who are you?",
            "model_used": "gpt-4o-mini",
        }
        r = client.post("/ask", json=payload, headers=headers)
    finally:
        ask_module.generate_answer = original

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "Hello from test"
    assert body["thread_id"] == thread_id
    assert body["usage"]["total_tokens"] == 15
    assert isinstance(body["sources"], list)
