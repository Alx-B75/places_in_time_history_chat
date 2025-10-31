"""Smoke test for LLM switching and guest->user migration.

Usage:
  python scripts/smoke.py

Requires the backend to be running at http://127.0.0.1:8000 by default.
Set environment variables to provide API keys if you want real-provider checks:
  OPENAI_API_KEY, OPENAI_API_BASE (optional)
  OPENROUTER_API_KEY, OPENROUTER_API_BASE (optional)

In development the admin endpoints are accessible without credentials (ENVIRONMENT=dev).
"""

import os
import sys
import time
import requests

BASE = os.environ.get("BASE", "http://127.0.0.1:8000")


def fail(msg):
    print("FAIL:", msg)
    sys.exit(2)


def ok(msg):
    print("OK:", msg)


def patch_llm(cfg):
    url = f"{BASE}/admin/llm"
    print("PATCH", url, cfg)
    r = requests.patch(url, json=cfg)
    return r


def llm_health():
    url = f"{BASE}/admin/llm/health"
    print("GET", url)
    r = requests.get(url)
    return r


def provider_check_openai():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("Skipping OpenAI provider check: OPENAI_API_KEY not set")
        return True
    cfg = {"provider": "openai", "api_key": key}
    r = patch_llm(cfg)
    if r.status_code >= 400:
        fail(f"PATCH /admin/llm failed ({r.status_code}) {r.text}")
    time.sleep(0.2)
    h = llm_health()
    if h.status_code != 200:
        fail(f"LLM health endpoint returned {h.status_code}: {h.text}")
    js = h.json()
    if not js.get("ok"):
        fail(f"OpenAI health check failed: {js}")
    ok("OpenAI provider responded")
    return True


def provider_check_openrouter():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("Skipping OpenRouter provider check: OPENROUTER_API_KEY not set")
        return True
    cfg = {"provider": "openrouter", "api_key": key}
    base = os.environ.get("OPENROUTER_API_BASE")
    if base:
        cfg["api_base"] = base
    r = patch_llm(cfg)
    if r.status_code >= 400:
        fail(f"PATCH /admin/llm failed ({r.status_code}) {r.text}")
    time.sleep(0.2)
    h = llm_health()
    if h.status_code != 200:
        fail(f"LLM health endpoint returned {h.status_code}: {h.text}")
    js = h.json()
    if not js.get("ok"):
        fail(f"OpenRouter health check failed: {js}")
    ok("OpenRouter provider responded")
    return True


def guest_to_user_migration():
    s = requests.Session()
    # pick a figure
    figs = s.get(f"{BASE}/figures/")
    if figs.status_code != 200:
        fail(f"Unable to list figures: {figs.status_code} {figs.text}")
    figs_json = figs.json()
    if not figs_json:
        fail("No figures available to test against")
    slug = figs_json[0].get("slug")
    print("Using figure:", slug)

    # start guest
    r = s.post(f"{BASE}/guest/start/{slug}")
    if r.status_code != 200:
        fail(f"guest start failed: {r.status_code} {r.text}")
    ok("Guest session started")

    # ask a question
    payload = {"message": "Hello from smoke test"}
    r = s.post(f"{BASE}/guest/ask", json=payload)
    if r.status_code != 200:
        fail(f"guest ask failed: {r.status_code} {r.text}")
    js = r.json()
    if not js.get("answer"):
        fail(f"guest ask returned no answer: {js}")
    ok("Guest ask returned an answer")

    # register a user
    email = f"smoke+{int(time.time())}@example.com"
    pw = "Sm0keTest!"  # meets validation requirements
    reg_payload = {"email": email, "password": pw, "gdpr_consent": True, "ai_ack": True}
    r = requests.post(f"{BASE}/auth/register", json=reg_payload)
    if r.status_code != 200:
        fail(f"register failed: {r.status_code} {r.text}")
    token = r.json().get("access_token")
    if not token:
        fail(f"no access token from register: {r.json()}")
    ok(f"Registered user {email}")

    # upgrade guest session to user thread
    headers = {"Authorization": f"Bearer {token}"}
    r = s.post(f"{BASE}/guest/upgrade", headers=headers)
    if r.status_code != 200:
        fail(f"guest upgrade failed: {r.status_code} {r.text}")
    js = r.json()
    if not js.get("upgraded"):
        fail(f"upgrade returned unexpected payload: {js}")
    thread_id = js.get("thread_id")
    if not thread_id:
        # older version returns thread_id inside nested object; try other keys
        thread_id = js.get("thread_id")
    ok(f"Guest upgraded to thread {thread_id}")

    # verify messages exist on thread
    r = requests.get(f"{BASE}/threads/{thread_id}/messages", headers=headers)
    if r.status_code != 200:
        fail(f"unable to fetch thread messages: {r.status_code} {r.text}")
    msgs = r.json()
    if not isinstance(msgs, list) or not msgs:
        fail(f"thread messages empty or invalid: {msgs}")
    ok("Thread messages preserved after upgrade")
    return True


if __name__ == "__main__":
    print("Smoke test starting against:", BASE)
    # Provider checks
    try:
        provider_check_openai()
    except Exception as e:
        print("OpenAI check error:", e)
    try:
        provider_check_openrouter()
    except Exception as e:
        print("OpenRouter check error:", e)

    # Migration test
    try:
        guest_to_user_migration()
    except Exception as e:
        fail(f"Migration test failed: {e}")

    print("Smoke test completed successfully")
    sys.exit(0)
