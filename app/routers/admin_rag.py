"""
Admin RAG context management (per-figure CRUD), admin-only.

Notes
-----
- Does NOT replace your existing /admin/rag/sources summary endpoint.
- Adds per-figure context CRUD under /admin/rag/contexts to avoid route conflicts.
- Create remains at your existing POST /admin/rag/sources (unchanged).
"""

from __future__ import annotations

from typing import Generator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

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
        ctx.source_name = patch.source_name
    if patch.source_url is not None:
        ctx.source_url = patch.source_url
    if patch.content_type is not None:
        ctx.content_type = patch.content_type
    if patch.content is not None:
        ctx.content = patch.content
    if patch.is_manual is not None:
        ctx.is_manual = int(patch.is_manual)

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
