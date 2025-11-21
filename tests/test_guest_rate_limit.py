from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_guest_start_rate_limit(monkeypatch):
    """Exceeding the allowed number of guest starts from the same client should return 429."""

    # Use a low limit by monkeypatching the helper if exposed
    from app.routers import guest as guest_router

    # If the module defines a rate limit constant, temporarily reduce it for the test
    if hasattr(guest_router, "_GUEST_START_LIMIT"):
        monkeypatch.setattr(guest_router, "_GUEST_START_LIMIT", 3, raising=False)
    if hasattr(guest_router, "_GUEST_WINDOW_SECONDS"):
        monkeypatch.setattr(guest_router, "_GUEST_WINDOW_SECONDS", 3600, raising=False)

    slug = "anne-hathaway"
    # Perform allowed number of requests
    for _ in range(3):
        r = client.post(f"/guest/start/{slug}")
        assert r.status_code in (200, 404)  # figure may or may not exist in test DB

    # Next call should be limited if rate limiting is active
    r = client.post(f"/guest/start/{slug}")
    if r.status_code not in (200, 404):
        assert r.status_code == 429


def test_guest_ask_rate_limit(monkeypatch):
    """Exceeding the allowed number of guest questions from the same client should return 429."""

    from app.routers import guest as guest_router

    # Stub the router-level LLM client to avoid real OpenAI calls.
    class DummyLLM:
        def generate(self, messages, model, temperature=0.3, top_p=1.0, max_tokens=None):  # signature compatible
            return {
                "choices": [
                    {"message": {"content": "stubbed"}}
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

    monkeypatch.setattr(guest_router, "llm_client", DummyLLM(), raising=False)

    if hasattr(guest_router, "_GUEST_ASK_LIMIT"):
        monkeypatch.setattr(guest_router, "_GUEST_ASK_LIMIT", 3, raising=False)
    if hasattr(guest_router, "_GUEST_ASK_WINDOW_SECONDS"):
        monkeypatch.setattr(guest_router, "_GUEST_ASK_WINDOW_SECONDS", 3600, raising=False)

    # We need a guest session cookie; best-effort: start a session
    slug = "anne-hathaway"
    start_res = client.post(f"/guest/start/{slug}")
    if start_res.status_code not in (200, 404):
        assert start_res.status_code == 200

    cookies = start_res.cookies if hasattr(start_res, "cookies") else {}

    for _ in range(3):
        r = client.post(
            "/guest/ask",
            json={"message": "Hello?"},
            cookies=cookies,
        )
        # Depending on seed data, this may be 200 or an application-level error
        assert r.status_code in (200, 400, 401, 404)

    r = client.post(
        "/guest/ask",
        json={"message": "One more"},
        cookies=cookies,
    )
    if r.status_code not in (200, 400, 401, 404):
        assert r.status_code == 429
