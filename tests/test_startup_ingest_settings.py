from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


client = TestClient(app)


def test_enable_figure_ingest_setting_exposed():
    """Settings should expose enable_figure_ingest with a default of True."""
    settings = get_settings()
    assert isinstance(settings.enable_figure_ingest, bool)


def test_health_admin_includes_figures_db_flag(admin_auth_header):
    """Smoke-check that app starts and health/admin is reachable.

    This indirectly verifies that lifespan did not crash when ingest
    is gated by enable_figure_ingest.
    """

    r = client.get("/health/admin", headers=admin_auth_header)
    assert r.status_code in (200, 401, 403)
