"""
Admin RAG context management (per-figure CRUD), admin-only.

Notes
-----
- Does NOT replace your existing /admin/rag/sources summary endpoint.
- Adds per-figure context CRUD under /admin/rag/contexts to avoid route conflicts.
- Create remains at your existing POST /admin/rag/sources (unchanged).
"""

from __future__ import annotations

from typing import Generator, List, Optional, Tuple, Dict

import re
import html as html_mod
import os
import tempfile
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app import models
from app.figures_database import FigureSessionLocal
from app.utils.security import get_admin_user

router = APIRouter(prefix="/admin/rag", tags=["Admin RAG"])


def get_figure_db() -> Generator[Session, None, None]:
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- upload job registry -------------------------------------------------
# lightweight in-memory job store for uploads -> background embedding job progress
# NOTE: this is process-local. For multi-instance deployments prefer Redis/persistent store.
_UPLOAD_JOBS: Dict[str, Dict] = {}


class UploadFileResult(BaseModel):
    filename: str
    type: str
    size: int
    ok: bool = True


class UploadResponse(BaseModel):
    results: List[UploadFileResult] = Field(default_factory=list)
    job_id: Optional[str] = None


def _html_to_text(html: str) -> str:
    # very small sanitizer / text extractor
    text = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.S | re.I)
    # strip tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _chunk_text(text: str, chunk_size: int = 750, overlap: int = 50) -> List[str]:
    tokens = text.split()
    out = []
    i = 0
    while i < len(tokens):
        chunk = tokens[i : i + chunk_size]
        out.append(" ".join(chunk))
        i += chunk_size - overlap
    return out


# Attempt fast PDF extraction via PyMuPDF, fall back to pdfminer if not available.
def _pdf_to_text(data: bytes) -> str:
    try:
        import fitz

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(data)
            tf.flush()
            path = tf.name
        doc = fitz.open(path)
        txt = []
        for p in doc:
            txt.append(p.get_text())
        doc.close()
        try:
            os.unlink(path)
        except Exception:
            pass
        return "\n".join(txt)
    except Exception:
        # fallback to pdfminer.six
        try:
            from pdfminer.high_level import extract_text

            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tf.write(data)
                tf.flush()
                path = tf.name
            text = extract_text(path)
            try:
                os.unlink(path)
            except Exception:
                pass
            return text
        except Exception:
            return ""


def _docx_to_text(data: bytes) -> str:
    try:
        from docx import Document

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(data)
            tf.flush()
            path = tf.name
        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs]
        try:
            os.unlink(path)
        except Exception:
            pass
        return "\n".join(paragraphs)
    except Exception:
        return ""


def _ingest_uploaded_text(
    db: Session,
    figure_slug: str,
    text: str,
    author: Optional[str] = None,
    source_name: Optional[str] = None,
    auto_embed: bool = False,
) -> Tuple[List[int], List[UploadFileResult]]:
    # create FigureContext rows for chunks produced from text, dedupe by exact text
    results: List[UploadFileResult] = []
    ctx_ids: List[int] = []
    if not text or not text.strip():
        return ctx_ids, results

    chunks = _chunk_text(text)
    for i, c in enumerate(chunks):
        row = models.FigureContext(
            figure_slug=figure_slug,
            text=c,
            author=author or "upload",
            source=source_name or "upload",
            is_embedded=False,
        )
        # dedupe: simple existence check
        exists = (
            db.query(models.FigureContext)
            .filter(models.FigureContext.figure_slug == figure_slug)
            .filter(models.FigureContext.text == c)
            .first()
        )
        if exists:
            results.append(
                UploadFileResult(filename=f"chunk-{i}", type="chunk", size=len(c), ok=False)
            )
            continue
        db.add(row)
        db.flush()
        ctx_ids.append(row.id)
        results.append(
            UploadFileResult(filename=f"chunk-{i}", type="chunk", size=len(c), ok=True)
        )
    db.commit()
    # Optionally embed synchronously
    if auto_embed and ctx_ids:
        # schedule synchronous embedding in current process (simple)
        try:
            from app.services.embedding_client import get_embedding
            from app.vector.chroma_client import ensure_collection

            emb = get_embedding
            coll = ensure_collection(figure_slug)
            rows = (
                db.query(models.FigureContext).filter(models.FigureContext.id.in_(ctx_ids)).all()
            )
            for r in rows:
                vec = emb(r.text)
                coll.add_documents([r.text], metadatas=[{"id": r.id}])
                r.is_embedded = True
            db.commit()
        except Exception:
            pass
    return ctx_ids, results


def _embed_context_ids(db: Session, ctx_ids: List[int], figure_slug: str) -> None:
    # embed by ids
    try:
        from app.services.embedding_client import get_embedding
        from app.vector.chroma_client import ensure_collection

        emb = get_embedding
        coll = ensure_collection(figure_slug)
        rows = db.query(models.FigureContext).filter(models.FigureContext.id.in_(ctx_ids)).all()
        for r in rows:
            vec = emb(r.text)
            coll.add_documents([r.text], metadatas=[{"id": r.id}])
            r.is_embedded = True
        db.commit()
    except Exception:
        db.rollback()



# ---------- Schemas ----------


class ContextRead(BaseModel):
    id: int
    figure_slug: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    content_type: Optional[str] = None
    content: Optional[str] = None
    is_manual: Optional[int] = 0
    is_embedded: Optional[bool] = False


class ContextCreate(BaseModel):
    figure_slug: str
    source_name: str
    source_url: Optional[str] = None
    content_type: str = Field(..., min_length=1, max_length=100)
    content: Optional[str] = None


class ContextUpdate(BaseModel):
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    content_type: Optional[str] = None
    content: Optional[str] = None
    is_manual: Optional[int] = None


# ---------- Endpoints ----------

@router.get("/contexts", response_model=List[ContextRead])
def list_contexts_by_figure(
    figure_slug: str = Query(..., min_length=1, description="Slug of the figure"),
    _: models.User = Depends(get_admin_user),
    db_fig: Session = Depends(get_figure_db),
) -> List[ContextRead]:
    """
    Return all FigureContext rows for a given figure.
    """
    rows = (
        db_fig.query(models.FigureContext)
        .filter(models.FigureContext.figure_slug == figure_slug)
        .order_by(models.FigureContext.id.asc())
        .all()
    )
    return rows  # type: ignore[return-value]


@router.patch("/contexts/{ctx_id}", response_model=ContextRead)
def update_context(
    ctx_id: int,
    patch: ContextUpdate,
    _: models.User = Depends(get_admin_user),
    db_fig: Session = Depends(get_figure_db),
) -> ContextRead:
    """
    Partially update one FigureContext.
    """
    ctx = db_fig.query(models.FigureContext).filter(models.FigureContext.id == ctx_id).first()
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")

    if patch.source_name is not None:
        ctx.source_name = patch.source_name  # type: ignore[assignment]
    if patch.source_url is not None:
        ctx.source_url = patch.source_url  # type: ignore[assignment]
    if patch.content_type is not None:
        ctx.content_type = patch.content_type  # type: ignore[assignment]
    if patch.content is not None:
        ctx.content = patch.content  # type: ignore[assignment]
    if patch.is_manual is not None:
        ctx.is_manual = int(patch.is_manual)  # type: ignore[assignment]

    db_fig.add(ctx)
    db_fig.commit()
    db_fig.refresh(ctx)
    return ctx  # type: ignore[return-value]


@router.delete("/contexts/{ctx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_context(
    ctx_id: int,
    _: models.User = Depends(get_admin_user),
    db_fig: Session = Depends(get_figure_db),
):
    """
    Delete a FigureContext by id.
    """
    ctx = db_fig.query(models.FigureContext).filter(models.FigureContext.id == ctx_id).first()
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")
    db_fig.delete(ctx)
    db_fig.commit()
    return None


# ---------- Admin UI helper endpoints ----------

class RagFigureSummary(BaseModel):
    slug: str
    name: Optional[str] = None
    total_contexts: int
    has_manual_context: bool
    context_counts: dict
    sources_meta: dict = Field(default_factory=dict)


class RagSummaryResponse(BaseModel):
    collection: dict
    figures: list[RagFigureSummary]


@router.get("/sources", response_model=RagSummaryResponse)
def rag_sources_summary(
    _: models.User = Depends(get_admin_user),
    db_fig: Session = Depends(get_figure_db),
):
    """
    Summarize RAG sources by figure for the Admin UI.

    Response shape matches static_frontend/admin.js expectations:
    { collection: {...}, figures: [...] }
    """
    # Collection info (best-effort)
    collection_info = {"ok": False, "detail": None, "name": None, "doc_count": None}
    try:
        from app.vector.chroma_client import get_figure_context_collection
        coll = get_figure_context_collection()
        collection_info["ok"] = True
        collection_info["name"] = getattr(coll, "name", None)
        try:
            # chroma collections typically have count() or peek(); guard both
            if hasattr(coll, "count"):
                collection_info["doc_count"] = coll.count()
            else:
                # Fallback: try peek() length
                peek = coll.peek() if hasattr(coll, "peek") else None
                if peek and isinstance(peek, dict):
                    docs = peek.get("documents") or []
                    collection_info["doc_count"] = sum(len(d or []) for d in docs)
        except Exception:
            pass
    except Exception as exc:
        collection_info["ok"] = False
        collection_info["detail"] = str(exc)

    # Build per-figure summaries
    figures: list[RagFigureSummary] = []
    # Fetch figures and contexts in bulk
    all_figs = db_fig.query(models.HistoricalFigure).all()
    # Map slug -> figure
    by_slug = {f.slug: f for f in all_figs if getattr(f, "slug", None)}
    # Preload contexts per figure slug
    ctx_rows = db_fig.query(models.FigureContext).all()
    grouped: dict[str, list[models.FigureContext]] = {}
    for r in ctx_rows:
        if not r.figure_slug:
            continue
        grouped.setdefault(r.figure_slug, []).append(r)

    for slug, figure in by_slug.items():
        rows = grouped.get(slug, [])
        counts: dict[str, int] = {}
        manual = False
        for r in rows:
            ctype = (r.content_type or "").strip().lower() or "unknown"
            counts[ctype] = counts.get(ctype, 0) + 1
            manual = manual or bool(getattr(r, "is_manual", 0))

        # Extract known links if present
        sources_meta = {}
        try:
            import json
            wiki_links = {}
            if getattr(figure, "wiki_links", None):
                wiki_links = json.loads(figure.wiki_links) if isinstance(figure.wiki_links, str) else (figure.wiki_links or {})
            sources_meta = {
                "wikipedia": wiki_links.get("wikipedia"),
                "wikidata": wiki_links.get("wikidata"),
                "dbpedia": wiki_links.get("dbpedia"),
            }
        except Exception:
            sources_meta = {}

        figures.append(
            RagFigureSummary(
                slug=slug,
                name=getattr(figure, "name", None),
                total_contexts=len(rows),
                has_manual_context=manual,
                context_counts=counts,
                sources_meta=sources_meta,
            )
        )

    return RagSummaryResponse(collection=collection_info, figures=figures)


@router.post("/sources", response_model=ContextRead, status_code=status.HTTP_201_CREATED)
def create_manual_source(
    payload: ContextCreate,
    _: models.User = Depends(get_admin_user),
    db_fig: Session = Depends(get_figure_db),
) -> ContextRead:
    """
    Create a manual FigureContext entry for a given figure.
    """
    # Ensure figure exists
    fig = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == payload.figure_slug).first()
    if not fig:
        raise HTTPException(status_code=404, detail="Figure not found")

    ctx = models.FigureContext(
        figure_slug=payload.figure_slug,
        source_name=payload.source_name,
        source_url=payload.source_url,
        content_type=payload.content_type,
        content=payload.content or "",
        is_manual=1,
    )
    db_fig.add(ctx)
    db_fig.commit()
    db_fig.refresh(ctx)
    return ctx  # type: ignore[return-value]


@router.post("/upload", response_model=list[ContextRead], status_code=status.HTTP_201_CREATED)
def upload_sources(
    figure_slug: str = Query(..., min_length=1, description="Slug of the figure to attach uploads to"),
    files: list[UploadFile] | None = None,
    _: models.User = Depends(get_admin_user),
    db_fig: Session = Depends(get_figure_db),
) -> list[ContextRead]:
    """
    Accept one or more uploaded files (PDFs etc), extract text (best-effort), and create FigureContext entries.

    This is a simple, robust helper to restore drag-and-drop ingestion from the admin UI.
    For PDFs we use PyPDF2 to extract text; other types fall back to raw bytes->utf-8 text.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Ensure figure exists
    fig = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == figure_slug).first()
    if not fig:
        raise HTTPException(status_code=404, detail="Figure not found")

    created: list[models.FigureContext] = []
    for up in files:
        filename = getattr(up, "filename", "uploaded") or "uploaded"
        content = ""
        try:
            # Try PDF extraction via PyPDF2 if file looks like PDF
            data = up.file.read()
            up.file.seek(0)
            if data[:4] == b"%PDF":
                try:
                    from PyPDF2 import PdfReader

                    reader = PdfReader(up.file)
                    pages = []
                    for p in reader.pages:
                        txt = p.extract_text() or ""
                        pages.append(txt)
                    content = "\n\n".join(pages)
                except Exception:
                    # Fallback to raw decode
                    try:
                        content = data.decode("utf-8", errors="replace")
                    except Exception:
                        content = ""
            else:
                # Non-PDF: try to decode as text
                try:
                    content = data.decode("utf-8", errors="replace")
                except Exception:
                    content = ""
        finally:
            try:
                up.file.close()
            except Exception:
                pass

        ctx = models.FigureContext(
            figure_slug=figure_slug,
            source_name=filename,
            source_url=None,
            content_type="document",
            content=content or "",
            is_manual=0,
        )
        db_fig.add(ctx)
        db_fig.commit()
        db_fig.refresh(ctx)
        created.append(ctx)

    # Optionally: caller can trigger background embedding/ingest; for now return created rows
    return created  # type: ignore[return-value]


@router.get("/upload-jobs/{job_id}")
async def upload_job_status(job_id: str):
    job = _UPLOAD_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/figure/{figure_slug}/upload", response_model=UploadResponse)
async def upload_figure_files(
    figure_slug: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    auto_embed: Optional[bool] = Query(False),
    db: Session = Depends(get_figure_db),
    _admin=Depends(get_admin_user),
):
    resp = UploadResponse()
    all_new_ctx_ids: List[int] = []
    for f in files:
        content = await f.read()
        ft = (f.filename or "").lower()
        if ft.endswith(".pdf"):
            text = _pdf_to_text(content)
            ctx_ids, results = _ingest_uploaded_text(db, figure_slug, text, source_name=f.filename, auto_embed=auto_embed)
        elif ft.endswith(".docx"):
            text = _docx_to_text(content)
            ctx_ids, results = _ingest_uploaded_text(db, figure_slug, text, source_name=f.filename, auto_embed=auto_embed)
        elif ft.endswith(".html") or ft.endswith(".htm"):
            text = _html_to_text(content.decode(errors="ignore"))
            ctx_ids, results = _ingest_uploaded_text(db, figure_slug, text, source_name=f.filename, auto_embed=auto_embed)
        else:
            # treat as plain text
            try:
                text = content.decode()
            except Exception:
                text = ""
            ctx_ids, results = _ingest_uploaded_text(db, figure_slug, text, source_name=f.filename, auto_embed=auto_embed)
        resp.results.extend(results)
        all_new_ctx_ids.extend(ctx_ids)

    # If not auto_embed, schedule background embedding job
    if all_new_ctx_ids and not auto_embed:
        job_id = uuid.uuid4().hex
        _UPLOAD_JOBS[job_id] = {"created_at": time.time(), "total": len(all_new_ctx_ids), "done": 0, "status": "queued"}

        def _bg(ctx_ids: List[int], jid: str):
            _UPLOAD_JOBS[jid]["status"] = "running"
            # embed in batches
            for i, cid in enumerate(ctx_ids):
                try:
                    _embed_context_ids(db, [cid], figure_slug)
                    _UPLOAD_JOBS[jid]["done"] += 1
                except Exception:
                    pass
            _UPLOAD_JOBS[jid]["status"] = "done"

        background_tasks.add_task(_bg, all_new_ctx_ids, job_id)
        resp.job_id = job_id

    return resp
