"""
Download database endpoint tests with isolated test data directory.
"""
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_download_db_serves_attachment() -> None:
    """
    Creates a temporary DATA_DIR with a placeholder figures.db and asserts the
    endpoint returns an attachment with content.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATA_DIR"] = tmpdir
        db_path = Path(tmpdir) / "figures.db"
        db_path.write_bytes(b"test-bytes")

        resp = client.get("/download_db")
        assert resp.status_code == 200, resp.text
        disp = resp.headers.get("content-disposition", "")
        assert "attachment" in disp.lower()
        assert "figures.db" in disp
        assert len(resp.content) > 0
