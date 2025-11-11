"""Figures API router for Places in Time History Chat."""

from typing import Generator, List

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.utils.security import get_current_user
from app.figures_database import FigureSessionLocal
from app.database import get_db_chat

router = APIRouter(prefix="/figures", tags=["Figures"])


def get_figure_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the figures database."""
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/",
    response_model=List[schemas.HistoricalFigureRead],
    status_code=status.HTTP_200_OK,
)
def list_figures(
    skip: int = Query(0, ge=0, description="Number of records to skip."),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return."),
    db: Session = Depends(get_figure_db),
) -> List[schemas.HistoricalFigureRead]:
    """Return a paginated list of historical figures."""
    return crud.get_all_figures(db, skip=skip, limit=limit)


@router.get(
    "/search",
    response_model=List[schemas.HistoricalFigureRead],
    status_code=status.HTTP_200_OK,
)
def search_figures(
    q: str = Query(..., min_length=1, description="Query string to match against name or slug."),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of matches to return."),
    db: Session = Depends(get_figure_db),
) -> List[schemas.HistoricalFigureRead]:
    """Return figures whose name or slug contains the query string (case-insensitive)."""
    return crud.search_figures(db, q, limit=limit)


# Favorites endpoints BEFORE slug routes to avoid any matching ambiguity
 


@router.get(
    "/{slug}",
    response_model=schemas.HistoricalFigureDetail,
    status_code=status.HTTP_200_OK,
)
def get_figure_by_slug(
    slug: str,
    db: Session = Depends(get_figure_db),
) -> schemas.HistoricalFigureDetail:
    """Return full details for a single historical figure."""
    figure = crud.get_figure_by_slug(db, slug=slug)
    if not figure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Figure not found",
        )
    return figure


@router.get("/{slug}/bio", status_code=status.HTTP_200_OK)
def get_figure_bio(
    slug: str,
    db: Session = Depends(get_figure_db),  # must be figures DB
) -> dict:
    """
    Return a concise description (bio/summary) for a given figure slug.
    """
    desc = crud.get_figure_description(db, slug)
    return {"slug": slug, "description": desc}


@router.get(
    "/favorites",
    response_model=List[schemas.FavoriteRead],
    status_code=status.HTTP_200_OK,
)
def list_favorites(
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """Return the authenticated user's favorited figures."""
    user_id_val = getattr(current_user, 'id', None)
    if hasattr(user_id_val, 'expression'):
        user_id_val = current_user.__dict__.get('id', None)
    if user_id_val is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return crud.get_favorites_by_user(db, int(user_id_val))


@router.post(
    "/favorites/{figure_slug}",
    response_model=schemas.FavoriteRead,
    status_code=status.HTTP_201_CREATED,
)
def add_favorite(
    figure_slug: str,
    db: Session = Depends(get_db_chat),  # chat DB for favorites table
    fig_db: Session = Depends(get_figure_db),  # figures DB for existence check
    current_user: models.User = Depends(get_current_user),
):
    """Add a figure to the authenticated user's favorites."""
    # Validate figure exists (optional but helpful)
    fig = crud.get_figure_by_slug(fig_db, slug=figure_slug)
    if not fig:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Figure not found")
    user_id_val = getattr(current_user, 'id', None)
    if hasattr(user_id_val, 'expression'):
        user_id_val = current_user.__dict__.get('id', None)
    if user_id_val is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return crud.add_favorite(db, int(user_id_val), figure_slug)


@router.delete(
    "/favorites/{figure_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_favorite(
    figure_slug: str,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a figure from the authenticated user's favorites."""
    user_id_val = getattr(current_user, 'id', None)
    if hasattr(user_id_val, 'expression'):
        user_id_val = current_user.__dict__.get('id', None)
    if user_id_val is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    ok = crud.remove_favorite(db, int(user_id_val), figure_slug)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

