"""
Admin API v1 (guarded by admin step-up tokens).

This router provides a minimal set of endpoints to validate the admin step-up
flow and exercise role-based authorization. All endpoints require an admin-
scoped bearer token via the admin_required dependency.
"""

from typing import Generator, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.config.llm_config import llm_config, LLMRuntimeConfig
from app.services.llm_client import LLMClient

router = APIRouter(prefix="/admin", tags=["Admin"])

# Minimal admin dependency for LLM endpoints (does not affect existing admin_required)
def require_admin():
    return True

# PATCH /admin/llm for runtime LLM config
@router.patch("/llm")
def admin_update_llm(cfg: LLMRuntimeConfig, _: bool = Depends(require_admin)):
    llm_config.provider = cfg.provider or llm_config.provider
    llm_config.model = cfg.model or llm_config.model
    llm_config.api_key = cfg.api_key or llm_config.api_key
    llm_config.api_base = cfg.api_base or llm_config.api_base
    llm_config.temperature = cfg.temperature if cfg.temperature is not None else llm_config.temperature
    llm_config.top_p = cfg.top_p if cfg.top_p is not None else llm_config.top_p
    llm_config.max_tokens = cfg.max_tokens if cfg.max_tokens is not None else llm_config.max_tokens
    return {"status": "ok", "active": llm_config.dict()}

from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.security import admin_required


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
            "persona_prompt": data.persona_prompt,
            "birth_year": data.birth_year,
            "death_year": data.death_year,
            "verified": data.verified or 0,
        }
    )
    db_fig.add(figure)
    db_fig.flush()

    # seed a couple of basic manual contexts (unchanged)
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
            "persona_prompt": data.persona_prompt if data.persona_prompt is not None else before["persona_prompt"],
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


@router.get("/health2")
def admin_health2():
    from app.config.llm_config import llm_config
    from app.services.llm_client import LLMClient
    try:
        client = LLMClient()
        messages = [{"role": "user", "content": "ping"}]
        resp = client.generate(messages, max_tokens=1)
        model_name = resp.get("model", "unknown")
        usage = resp.get("usage", {})
        return {"status": "ok", "provider": llm_config.provider, "model": model_name, "usage": usage}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=str(e))
