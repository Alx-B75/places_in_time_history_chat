from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_admin_ui_is_public():
    r = client.get("/admin/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")

def test_ops_console_is_public():
    r = client.get("/ops/console")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_admin_figures_ui_is_public():
    r = client.get("/admin/figures-ui")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_admin_figure_edit_ui_is_public():
    r = client.get("/admin/figure-ui/test-slug")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
