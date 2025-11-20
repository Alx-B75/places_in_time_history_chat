import importlib
import os


def test_seed_does_not_overwrite_existing_db(tmp_path, monkeypatch):
    # Simulate DATA_DIR / figures mount with a pre-existing figures.db
    db_path = tmp_path / "figures.db"
    db_path.write_text("PERSIST")

    # Point FIGURES_DB_PATH to our temp location so figures_database resolves here
    monkeypatch.setenv("FIGURES_DB_PATH", str(db_path))

    # Ensure the file really exists before import/seed
    assert db_path.exists()

    # Import startup_ingest and force maybe_ingest_seed_csv to run against this DB.
    # Its logic should *not* delete or replace an existing figures.db; it only
    # creates/updates rows in-place.
    init_module = importlib.import_module("app.startup_ingest")
    importlib.reload(init_module)
    ran, _ = init_module.maybe_ingest_seed_csv(logger=None)

    # Regardless of whether ingestion ran, the underlying file contents should not be
    # replaced by a different file. We assert that the sentinel content is still there.
    assert db_path.read_text().startswith("PERSIST")
