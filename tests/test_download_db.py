"""Download database endpoint tests with isolated test data directory."""

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _set_temp_data_dir(tmp_path: Path) -> Path:
    """Point DATA_DIR at a tmp path and create a dummy figures.db file there."""
    os.environ["DATA_DIR"] = str(tmp_path)
    db_path = tmp_path / "figures.db"
    db_path.write_bytes(b"test-bytes")
    return db_path


def test_download_db_requires_auth(tmp_path) -> None:
    """Unauthenticated requests to /download_db should be rejected."""
    _set_temp_data_dir(tmp_path)
    resp = client.get("/download_db")
    assert resp.status_code in (401, 403)


def test_download_db_admin_can_download(tmp_path, admin_auth_header) -> None:
    """Authenticated admin user can download the figures database file."""
    _set_temp_data_dir(tmp_path)

    resp = client.get("/download_db", headers=admin_auth_header)
    assert resp.status_code == 200, resp.text

    disp = resp.headers.get("content-disposition", "")
    assert "attachment" in disp.lower()
    assert "figures.db" in disp
    assert len(resp.content) > 0
