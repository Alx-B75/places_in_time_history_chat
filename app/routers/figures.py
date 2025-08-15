"""Figures API router for Places in Time History Chat."""

from typing import Generator, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.figures_database import FigureSessionLocal

router = APIRouter(prefix="/figures", tags=["Figures"])


def get_figure_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the figures database."""
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[schemas.HistoricalFigureRead], status_code=status.HTTP_200_OK)
def list_figures(
    skip: int = Query(0, ge=0, description="Number of records to skip."),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return."),
    db: Session = Depends(get_figure_db),
) -> List[schemas.HistoricalFigureRead]:
    """Return a paginated list of historical figures."""
    return crud.get_all_figures(db, skip=skip, limit=limit)


@router.get("/search", response_model=List[schemas.HistoricalFigureRead], status_code=status.HTTP_200_OK)
def search_figures(
    q: str = Query(..., min_length=1, description="Query string to match against name or slug."),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of matches to return."),
    db: Session = Depends(get_figure_db),
) -> List[schemas.HistoricalFigureRead]:
    """Return figures whose name or slug contains the query string (case-insensitive)."""
    return crud.search_figures(db, q, limit=limit)


@router.get("/{slug}", response_model=schemas.HistoricalFigureDetail, status_code=status.HTTP_200_OK)
def get_figure_by_slug(
    slug: str,
    db: Session = Depends(get_figure_db),
) -> schemas.HistoricalFigureDetail:
    """Return full details for a single historical figure."""
    figure = crud.get_figure_by_slug(db, slug=slug)
    if not figure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Figure not found")
    return figure
