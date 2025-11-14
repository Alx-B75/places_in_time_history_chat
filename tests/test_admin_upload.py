import os
from fastapi.testclient import TestClient

from app.main import app
from app.figures_database import FigureSessionLocal
from app import models


class DummyCollection:
    def __init__(self):
        self.docs = []

    def add(self, documents=None, embeddings=None, metadatas=None, ids=None):
        self.docs.append({
            "documents": documents or [],
            "embeddings": embeddings or [],
            "metadatas": metadatas or [],
            "ids": ids or [],
        })


def ensure_figure(slug: str = "upload-fig", name: str = "Upload Figure"):
    db = FigureSessionLocal()
    try:
        existing = db.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == slug).first()
        if existing:
            return existing
        fig = models.HistoricalFigure(
            name=name,
            slug=slug,
            short_summary="test",
            wiki_links='{}',
        )
        db.add(fig)
        db.commit()
        db.refresh(fig)
        return fig
    finally:
        db.close()


def test_admin_upload_text_monkeypatched_chroma(monkeypatch):
    # Force dev bypass for admin_required
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # Ensure figure present
    fig = ensure_figure()

    # Monkeypatch chroma collection to avoid dimension and I/O issues
    dummy = DummyCollection()
    monkeypatch.setattr("app.vector.chroma_client.get_figure_context_collection", lambda: dummy)

    client = TestClient(app)

    files = [
        (
            "files",
            ("sample.txt", b"This is a small test document. " * 200, "text/plain"),
        )
    ]
    resp = client.post(f"/admin/rag/figure/{fig.slug}/upload", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_created"] >= 1
    assert data["total_skipped"] >= 0
    # Either embedded now or queued; both are acceptable
    assert "files" in data and len(data["files"]) == 1
    assert data["files"][0]["name"].startswith("sample")