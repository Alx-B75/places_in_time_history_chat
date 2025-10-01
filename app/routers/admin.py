"""
Admin API v1 (guarded by admin step-up tokens).

This router provides a minimal set of endpoints to validate the admin step-up
flow and exercise role-based authorization. All endpoints require an admin-
scoped bearer token via the admin_required dependency.

This version adds:
- GET /admin/rag/sources   → list current RAG sources and Chroma availability
- POST /admin/rag/sources  → create a manual RAG source (FigureContext, is_manual=1)
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Generator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.security import admin_required

# Chroma probe (safe, no secrets)
from app.vector.chroma_client import get_figure_context_collection

router = APIRouter(prefix="/admin", tags=["Admin"])


def get_figure_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session bound to the figures database.
    """
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
def admin_health(_: models.User = Depends(admin_required)) -> dict:
    """
    Return a simple health payload to confirm admin access.
    """
    return {"ok": True, "scope": "admin"}


@router.get("/users", response_model=List[schemas.UserRead])
def list_users(
    _: models.User = Depends(admin_required),
    db_chat: Session = Depends(get_db_chat),
) -> List[schemas.UserRead]:
    """
    List all users for administration.
    """
    return db_chat.query(models.User).order_by(models.User.id.asc()).all()


@router.patch("/users/{user_id}/role", response_model=schemas.UserRead)
def update_user_role(
    user_id: int,
    payload: schemas.UserRoleUpdate,
    request: Request,
    admin_user: models.User = Depends(admin_required),
    db_chat: Session = Depends(get_db_chat),
) -> schemas.UserRead:
    """
    Update a user's role. Requires admin scope.
    """
    user = db_chat.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    previous = user.role
    user.role = payload.role
    db_chat.add(user)
    db_chat.add(
        models.AuditLog(
            actor_user_id=admin_user.id,
            action="user.role.update",
            object_type="user",
            object_id=str(user.id),
            diff_json=f'{{"before":"{previous}","after":"{user.role}"}}',
            ip=request.client.host if request.client else None,
        )
    )
    db_chat.commit()
    db_chat.refresh(user)
    return user


@router.get("/figures", response_model=List[schemas.HistoricalFigureRead])
def list_figures_admin(
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
) -> List[schemas.HistoricalFigureRead]:
    """
    List all historical figures for administration.
    """
    return db_fig.query(models.HistoricalFigure).order_by(models.HistoricalFigure.id.asc()).all()


@router.post("/figures", response_model=schemas.HistoricalFigureDetail, status_code=status.HTTP_201_CREATED)
def create_figure_admin(
    data: schemas.HistoricalFigureDetail,
    request: Request,
    admin_user: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
    db_chat: Session = Depends(get_db_chat),
) -> schemas.HistoricalFigureDetail:
    """
    Create a new historical figure.
    """
    slug = (data.slug or "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="slug is required")
    existing = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Figure with this slug already exists")

    figure = models.HistoricalFigure()
    figure.from_dict(
        {
            "name": data.name,
            "slug": slug,
            "main_site": data.main_site,
            "related_sites": [],
            "era": data.era,
            "roles": [],
            "short_summary": data.short_summary,
            "long_bio": data.long_bio,
            "echo_story": data.echo_story,
            "image_url": data.image_url,
            "sources": {},
            "wiki_links": {},
            "quote": data.quote,
            "birth_year": data.birth_year,
            "death_year": data.death_year,
            "verified": data.verified or 0,
        }
    )
    db_fig.add(figure)
    db_fig.flush()

    db_fig.add(
        models.FigureContext(
            figure_slug=slug,
            source_name="persona",
            source_url=None,
            content_type="persona",
            content=(data.long_bio or "")[:2000] if data.long_bio else "",
            is_manual=1,
        )
    )
    db_fig.add(
        models.FigureContext(
            figure_slug=slug,
            source_name="quote",
            source_url=None,
            content_type="instruction",
            content=(data.quote or "")[:500] if data.quote else "",
            is_manual=1,
        )
    )

    db_chat.add(
        models.AuditLog(
            actor_user_id=admin_user.id,
            action="figure.create",
            object_type="figure",
            object_id=slug,
            diff_json=None,
            ip=request.client.host if request.client else None,
        )
    )

    db_fig.commit()
    db_chat.commit()

    out = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == slug).first()
    return out  # type: ignore[return-value]


@router.patch("/figures/{slug}", response_model=schemas.HistoricalFigureDetail)
def update_figure_admin(
    slug: str,
    data: schemas.HistoricalFigureUpdate,
    request: Request,
    admin_user: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
    db_chat: Session = Depends(get_db_chat),
) -> schemas.HistoricalFigureDetail:
    """
    Partially update a historical figure by slug.
    """
    figure = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == slug).first()
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")

    before = figure.to_dict()
    figure.from_dict(
        {
            "name": data.name or before["name"],
            "slug": slug,
            "main_site": data.main_site if data.main_site is not None else before["main_site"],
            "related_sites": before["related_sites"],
            "era": data.era if data.era is not None else before["era"],
            "roles": before["roles"],
            "short_summary": data.short_summary if data.short_summary is not None else before["short_summary"],
            "long_bio": data.long_bio if data.long_bio is not None else before["long_bio"],
            "echo_story": data.echo_story if data.echo_story is not None else before["echo_story"],
            "image_url": data.image_url if data.image_url is not None else before["image_url"],
            "sources": before["sources"],
            "wiki_links": before["wiki_links"],
            "quote": data.quote if data.quote is not None else before["quote"],
            "birth_year": data.birth_year if data.birth_year is not None else before["birth_year"],
            "death_year": data.death_year if data.death_year is not None else before["death_year"],
            "verified": data.verified if data.verified is not None else int(before["verified"]),
        }
    )

    db_chat.add(
        models.AuditLog(
            actor_user_id=admin_user.id,
            action="figure.update",
            object_type="figure",
            object_id=slug,
            diff_json=None,
            ip=request.client.host if request.client else None,
        )
    )

    db_fig.commit()
    db_chat.commit()
    db_fig.refresh(figure)
    return figure  # type: ignore[return-value]


@router.delete("/figures/{slug}")
def delete_figure_admin(
    slug: str,
    request: Request,
    admin_user: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
    db_chat: Session = Depends(get_db_chat),
) -> Response:
    """
    Delete a historical figure by slug.
    """
    figure = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == slug).first()
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")

    db_fig.delete(figure)
    db_chat.add(
        models.AuditLog(
            actor_user_id=admin_user.id,
            action="figure.delete",
            object_type="figure",
            object_id=slug,
            diff_json=None,
            ip=request.client.host if request.client else None,
        )
    )

    db_fig.commit()
    db_chat.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------
# RAG Sources: Admin endpoints
# ---------------------------

class RagSourceCreate(BaseModel):
    figure_slug: str = Field(..., min_length=1)
    source_name: str = Field(..., min_length=1, max_length=200)
    content_type: str = Field(..., min_length=1, max_length=50)  # e.g., persona, instruction, bio, note, context
    content: str = Field(..., min_length=1)
    source_url: Optional[str] = Field(None, max_length=1000)


@router.get("/rag/sources")
def list_rag_sources(
    _: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
):
    """
    List current RAG sources by figure, plus Chroma collection availability.
    """
    # Figures
    figures = db_fig.query(models.HistoricalFigure).all()
    figures_by_slug = {f.slug: f for f in figures}

    # Contexts
    ctx_rows = db_fig.query(models.FigureContext).all()

    # Aggregate counts per figure and per content_type
    agg: Dict[str, Dict[str, int]] = {}
    manual_flags: Dict[str, bool] = {}
    for r in ctx_rows:
        slug = r.figure_slug or ""
        if slug not in agg:
            agg[slug] = {}
        ct = (r.content_type or "unknown").strip().lower()
        agg[slug][ct] = agg[slug].get(ct, 0) + 1
        if r.is_manual:
            manual_flags[slug] = True

    # Build response entries
    figure_entries: List[dict] = []
    for slug, fig in figures_by_slug.items():
        counts = agg.get(slug, {})
        total = sum(counts.values()) if counts else 0
        # Decode historical_figures.sources JSON safely; read-only
        try:
            sources_meta = json.loads(fig.sources) if fig.sources else {}
        except Exception:
            sources_meta = {}
        entry = {
            "slug": slug,
            "name": fig.name,
            "context_counts": counts,
            "total_contexts": total,
            "has_manual_context": bool(manual_flags.get(slug, False)),
            "sources_meta": sources_meta,
        }
        figure_entries.append(entry)

    # Chroma availability probe (collection-level only; no secrets)
    collection_info = {
        "name": "figure_context_collection",
        "available": False,
        "detail": None,
        "vector_index_stats": None,  # kept null; per-figure stats not cheap/standard
    }
    try:
        col = get_figure_context_collection()
        _ = col.name  # touch property to ensure client is alive
        collection_info["available"] = True
    except Exception as exc:  # pragma: no cover
        collection_info["available"] = False
        collection_info["detail"] = str(exc)

    return {
        "collection": collection_info,
        "figures": sorted(figure_entries, key=lambda x: x["slug"]),
    }


@router.post("/rag/sources", status_code=status.HTTP_201_CREATED)
def create_rag_source(
    payload: RagSourceCreate,
    request: Request,
    admin_user: models.User = Depends(admin_required),
    db_fig: Session = Depends(get_figure_db),
    db_chat: Session = Depends(get_db_chat),
):
    """
    Create a manual, admin-curated RAG source by inserting a FigureContext row.

    - Writes to figures DB only (FigureContext with is_manual=1)
    - Adds an AuditLog entry in chat DB
    - Idempotency: if an identical manual record already exists (same figure_slug,
      source_name, content_type, and content hash), returns 409.
    """
    slug = payload.figure_slug.strip()
    if not slug:
        raise HTTPException(status_code=400, detail="figure_slug is required")

    figure = db_fig.query(models.HistoricalFigure).filter(models.HistoricalFigure.slug == slug).first()
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")

    # Controlled vocabulary is enforced lightly here (no schema change).
    # You can widen this list later.
    allowed_types = {"persona", "instruction", "bio", "note", "quote", "context"}
    ctype = payload.content_type.strip().lower()
    if ctype not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"content_type must be one of {sorted(allowed_types)}",
        )

    # Idempotency via content hash (not stored in schema; logged in AuditLog)
    norm_text = payload.content.replace("\r\n", "\n").strip()
    content_hash = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()

    # Check for duplicate: same slug, source_name, content_type, AND identical content
    dup = (
        db_fig.query(models.FigureContext)
        .filter(
            models.FigureContext.figure_slug == slug,
            models.FigureContext.source_name == payload.source_name,
            models.FigureContext.content_type == ctype,
            models.FigureContext.content == norm_text,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="Identical manual source already exists")

    ctx = models.FigureContext(
        figure_slug=slug,
        source_name=payload.source_name,
        source_url=payload.source_url,
        content_type=ctype,
        content=norm_text,
        is_manual=1,
    )
    db_fig.add(ctx)
    db_fig.flush()  # get ctx.id

    db_chat.add(
        models.AuditLog(
            actor_user_id=admin_user.id,
            action="rag.source.create",
            object_type="figure_context",
            object_id=str(ctx.id),
            diff_json=json.dumps(
                {
                    "figure_slug": slug,
                    "source_name": payload.source_name,
                    "content_type": ctype,
                    "content_hash": content_hash,
                    "source_url": payload.source_url,
                }
            ),
            ip=request.client.host if request.client else None,
        )
    )

    db_fig.commit()
    db_chat.commit()

    return {
        "ok": True,
        "id": ctx.id,
        "figure_slug": slug,
        "source_name": ctx.source_name,
        "content_type": ctx.content_type,
        "is_manual": True,
    }
