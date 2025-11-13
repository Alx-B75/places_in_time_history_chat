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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import re
import html as html_mod
import requests

from app import models
from app.figures_database import FigureSessionLocal
from app.utils.security import admin_required

router = APIRouter(prefix="/admin/rag", tags=["Admin RAG"])


def get_figure_db() -> Generator[Session, None, None]:
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Schemas ----------

class ContextRead(BaseModel):
    id: int
    figure_slug: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    content_type: Optional[str] = None
    content: Optional[str] = None
    is_manual: int

    class Config:
        from_attributes = True


class ContextUpdate(BaseModel):
    source_name: Optional[str] = Field(None, max_length=200)
    source_url: Optional[str] = None  # keep free-form URL (some may be non-HTTP)
    content_type: Optional[str] = Field(None, max_length=100)
    content: Optional[str] = None
    is_manual: Optional[int] = None


class ContextCreate(BaseModel):
    figure_slug: str = Field(..., min_length=1)
    source_name: str = Field(..., min_length=1, max_length=200)
    content_type: str = Field(..., min_length=1, max_length=100)
    source_url: Optional[str] = None
    content: Optional[str] = None


# ---------- Endpoints ----------

@router.get("/contexts", response_model=List[ContextRead])
def list_contexts_by_figure(
    figure_slug: str = Query(..., min_length=1, description="Slug of the figure"),
    _: models.User = Depends(admin_required),
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
    _: models.User = Depends(admin_required),
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
    _: models.User = Depends(admin_required),
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
    _: models.User = Depends(admin_required),
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


class FigureRagDetail(BaseModel):
    figure: dict
    sources_meta: dict
    contexts: list[ContextRead]
    embeddings: dict


@router.get("/figure/{figure_slug}/detail", response_model=FigureRagDetail)
def rag_figure_detail(
    figure_slug: str,
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
):
    """
    Return a consolidated RAG view for a single figure, including:
    - figure metadata
    - known source links (wikipedia/wikidata/dbpedia)
    - contexts list
    - embedding info from Chroma (ids and count)
    """
    fig = (
        db_fig.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == figure_slug)
        .first()
    )
    if not fig:
        raise HTTPException(status_code=404, detail="Figure not found")

    # contexts
    ctx_rows = (
        db_fig.query(models.FigureContext)
        .filter(models.FigureContext.figure_slug == figure_slug)
        .order_by(models.FigureContext.id.asc())
        .all()
    )
    contexts: list[ContextRead] = [ContextRead.model_validate(r) for r in ctx_rows]  # type: ignore[arg-type]

    # sources_meta (wiki links)
    sources_meta = {}
    try:
        import json
        wiki_links = {}
        if getattr(fig, "wiki_links", None):
            wiki_links = json.loads(fig.wiki_links) if isinstance(fig.wiki_links, str) else (fig.wiki_links or {})
        sources_meta = {
            "wikipedia": wiki_links.get("wikipedia"),
            "wikidata": wiki_links.get("wikidata"),
            "dbpedia": wiki_links.get("dbpedia"),
        }
    except Exception:
        sources_meta = {}

    # embeddings from Chroma
    emb_info = {"count": 0, "ids": [], "has_more": False}
    try:
        from app.vector.chroma_client import get_figure_context_collection
        coll = get_figure_context_collection()
        # fetch up to 1000 ids for this figure
        got = coll.get(where={"figure_slug": figure_slug}, limit=1000)
        ids = list(got.get("ids", []) or [])
        emb_info["ids"] = ids
        emb_info["count"] = len(ids)
        # naive "has_more": if limit boundary reached
        emb_info["has_more"] = len(ids) >= 1000
    except Exception:
        pass

    return FigureRagDetail(
        figure=getattr(fig, "to_dict", lambda: {} )(),
        sources_meta=sources_meta,
        contexts=contexts,
        embeddings=emb_info,
    )


# ---------- Embedding helpers and endpoints ----------

def _chunk_text(text: str, max_len: int = 1600, overlap: int = 200) -> List[str]:
    text = text.strip()
    if not text:
        return []
    parts: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + max_len)
        parts.append(text[i:j])
        if j >= n:
            break
        i = max(0, j - overlap)
    return parts


def _html_to_text(html: str) -> str:
    # Very light HTML to text conversion; avoids extra deps
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class EmbedResult(BaseModel):
    embedded: int
    detail: Optional[str] = None


@router.post("/contexts/{ctx_id}/embed", response_model=EmbedResult)
def embed_context(
    ctx_id: int,
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
):
    ctx = db_fig.query(models.FigureContext).filter(models.FigureContext.id == ctx_id).first()
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")
    if not ctx.content:
        raise HTTPException(status_code=400, detail="Context has no content to embed")
    from app.vector.chroma_client import get_figure_context_collection
    from app.vector.embedding_provider import get_embedding
    coll = get_figure_context_collection()
    vec_id = f"{ctx.figure_slug}-{ctx.id}"
    try:
        # delete previous if exists; ignore errors
        try:
            coll.delete(ids=[vec_id])
        except Exception:
            pass
        emb = get_embedding(ctx.content)
        meta = {
            "figure_slug": ctx.figure_slug,
            "source_name": getattr(ctx, "source_name", None),
            "source_url": getattr(ctx, "source_url", None),
            "content_type": getattr(ctx, "content_type", None),
            "is_manual": bool(getattr(ctx, "is_manual", 0)),
        }
        coll.add(documents=[ctx.content], embeddings=[emb], metadatas=[meta], ids=[vec_id])
        return EmbedResult(embedded=1)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Embed failed: {exc}")


@router.post("/figure/{figure_slug}/embed-all", response_model=EmbedResult)
def embed_all_for_figure(
    figure_slug: str,
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
):
    rows = (
        db_fig.query(models.FigureContext)
        .filter(models.FigureContext.figure_slug == figure_slug)
        .all()
    )
    from app.vector.chroma_client import get_figure_context_collection
    from app.vector.embedding_provider import get_embedding
    coll = get_figure_context_collection()
    embedded = 0
    for ctx in rows:
        if not ctx.content:
            continue
        vec_id = f"{ctx.figure_slug}-{ctx.id}"
        try:
            try:
                coll.delete(ids=[vec_id])
            except Exception:
                pass
            emb = get_embedding(ctx.content)
            meta = {
                "figure_slug": ctx.figure_slug,
                "source_name": getattr(ctx, "source_name", None),
                "source_url": getattr(ctx, "source_url", None),
                "content_type": getattr(ctx, "content_type", None),
                "is_manual": bool(getattr(ctx, "is_manual", 0)),
            }
            coll.add(documents=[ctx.content], embeddings=[emb], metadatas=[meta], ids=[vec_id])
            embedded += 1
        except Exception:
            # continue with best-effort embedding
            continue
    return EmbedResult(embedded=embedded)


class IngestSourceRequest(BaseModel):
    source: str = Field(..., description="wikipedia | generic")
    url: Optional[str] = None
    max_chunks: Optional[int] = Field(default=20, ge=1, le=200)


class IngestSourceResponse(BaseModel):
    created: int
    skipped: int
    embedded: int


@router.post("/figure/{figure_slug}/ingest-source", response_model=IngestSourceResponse)
def ingest_source_for_figure(
    figure_slug: str,
    payload: IngestSourceRequest,
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
):
    fig = (
        db_fig.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == figure_slug)
        .first()
    )
    if not fig:
        raise HTTPException(status_code=404, detail="Figure not found")

    source = (payload.source or "").lower().strip()
    url = (payload.url or "").strip()
    # Resolve URL from stored links if not provided
    if source == "wikipedia" and not url:
        try:
            import json
            wiki_links = json.loads(fig.wiki_links) if getattr(fig, "wiki_links", None) else {}
            url = (wiki_links or {}).get("wikipedia") or ""
        except Exception:
            url = ""
    if not url:
        raise HTTPException(status_code=400, detail="No URL available to ingest")

    created, skipped, embedded = _ingest_single_url(db_fig, figure_slug, source, url, payload.max_chunks)
    return IngestSourceResponse(created=created, skipped=skipped, embedded=embedded)


# Clean manual source creation endpoint
@router.post("/sources", response_model=ContextRead, status_code=status.HTTP_201_CREATED)
def create_manual_source(
    payload: ContextCreate,
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
) -> ContextRead:
    """
    Create a manual FigureContext entry for a given figure.
    """
    fig = (
        db_fig.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == payload.figure_slug)
        .first()
    )
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


# Shared helper for ingestion of a single URL with chunking, dedupe, and embedding
def _ingest_single_url(db_fig: Session, figure_slug: str, source: str, url: str, max_chunks: Optional[int]) -> Tuple[int, int, int]:
    headers = {
        "User-Agent": "PlacesInTimeBot/1.0 (+https://example.com/admin; contact: admin@example.com)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, timeout=20, headers=headers)
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {exc}")

    text = _html_to_text(resp.text)
    if not text:
        raise HTTPException(status_code=400, detail="No text extracted from source")

    chunks = _chunk_text(text)
    if max_chunks:
        chunks = chunks[: max_chunks]

    existing = (
        db_fig.query(models.FigureContext)
        .filter(models.FigureContext.figure_slug == figure_slug)
        .filter(models.FigureContext.source_url == url)
        .all()
    )
    existing_texts = set((r.content or "").strip() for r in existing if r.content)

    created = 0
    new_rows: List[models.FigureContext] = []
    for chunk in chunks:
        if chunk.strip() in existing_texts:
            continue
        ctx = models.FigureContext(
            figure_slug=figure_slug,
            source_name=source,
            source_url=url,
            content_type="context",
            content=chunk,
            is_manual=0,
        )
        db_fig.add(ctx)
        db_fig.flush()
        new_rows.append(ctx)
        existing_texts.add(chunk.strip())
        created += 1
    db_fig.commit()

    from app.vector.chroma_client import get_figure_context_collection
    from app.vector.embedding_provider import get_embedding
    coll = get_figure_context_collection()
    embedded = 0
    for ctx in new_rows:
        try:
            emb = get_embedding(ctx.content or "")
            meta = {
                "figure_slug": ctx.figure_slug,
                "source_name": getattr(ctx, "source_name", None),
                "source_url": getattr(ctx, "source_url", None),
                "content_type": getattr(ctx, "content_type", None),
                "is_manual": bool(getattr(ctx, "is_manual", 0)),
            }
            vec_id = f"{ctx.figure_slug}-{ctx.id}"
            coll.add(documents=[ctx.content or ""], embeddings=[emb], metadatas=[meta], ids=[vec_id])
            embedded += 1
        except Exception:
            continue
    skipped = len(chunks) - created
    return created, skipped, embedded


class IngestAllResponse(BaseModel):
    per_source: Dict[str, IngestSourceResponse]
    total_created: int
    total_skipped: int
    total_embedded: int


@router.post("/figure/{figure_slug}/ingest-all", response_model=IngestAllResponse)
def ingest_all_links_for_figure(
    figure_slug: str,
    max_chunks: int = 20,
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
):
    fig = (
        db_fig.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == figure_slug)
        .first()
    )
    if not fig:
        raise HTTPException(status_code=404, detail="Figure not found")
    try:
        import json
        wiki_links = json.loads(fig.wiki_links) if getattr(fig, "wiki_links", None) else {}
    except Exception:
        wiki_links = {}
    sources_to_try = [
        ("wikipedia", wiki_links.get("wikipedia")),
        ("generic", wiki_links.get("wikidata")),
        ("generic", wiki_links.get("dbpedia")),
    ]
    per: Dict[str, IngestSourceResponse] = {}
    totals = {"created": 0, "skipped": 0, "embedded": 0}
    for label, url in sources_to_try:
        if not url:
            continue
        c, s, e = _ingest_single_url(db_fig, figure_slug, label, url, max_chunks)
        per[url] = IngestSourceResponse(created=c, skipped=s, embedded=e)
        totals["created"] += c
        totals["skipped"] += s
        totals["embedded"] += e
    return IngestAllResponse(per_source=per, total_created=totals["created"], total_skipped=totals["skipped"], total_embedded=totals["embedded"])


class EmbeddingHealth(BaseModel):
    provider: str
    model: str
    dimension: int
    ready: bool


@router.get("/embedding/health", response_model=EmbeddingHealth)
def embedding_health(
    _: models.User = Depends(admin_required),
):
    from app.services.embedding_client import EmbeddingClient
    client = EmbeddingClient()
    provider = client.provider
    model = "text-embedding-3-small" if provider == "openai" else "all-MiniLM-L6-v2"
    dim = client.get_embedding_dimension()
    ready = client.client is not None
    return EmbeddingHealth(provider=provider, model=model, dimension=dim, ready=ready)
