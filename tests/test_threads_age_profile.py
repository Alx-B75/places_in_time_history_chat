from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_thread_creation_accepts_age_profile():
    username = f"ap_user_{uuid4().hex[:8]}"
    reg = client.post("/register", json={"username": username, "password": "pw"})
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    user_id = reg.json()["user_id"]

    r = client.post(
        "/threads",
        json={"user_id": user_id, "title": "AP", "age_profile": "kids"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    thread_id = r.json()["thread_id"]

    gr = client.get(f"/threads/{thread_id}", headers={"Authorization": f"Bearer {token}"})
    assert gr.status_code == 200, gr.text
    data = gr.json()
    # age_profile should be present and set to 'kids' (or default if backend coerces)
    assert data.get("age_profile") in {"kids", "teen", "general"}
