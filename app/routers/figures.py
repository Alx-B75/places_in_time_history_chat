"""Figures API router for Places in Time History Chat."""

from typing import Generator, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.figures_database import FigureSessionLocal

router = APIRouter(
    prefix="/figures",
    tags=["Figures"],
)


def get_figure_db() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy session bound to the figures database.

    Ensures the session is closed after request handling completes.

    Yields:
        Session: SQLAlchemy session for read operations.
    """
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
    """
    Return a paginated list of historical figures.

    Args:
        skip: Number of records to skip from the beginning.
        limit: Maximum number of records to return.
        db: Figures database session.

    Returns:
        A list of figure summaries suitable for listings and selectors.
    """
    return crud.get_all_figures(db, skip=skip, limit=limit)


@router.get(
    "/{slug}",
    response_model=schemas.HistoricalFigureDetail,
    status_code=status.HTTP_200_OK,
)
def get_figure_by_slug(
    slug: str,
    db: Session = Depends(get_figure_db),
) -> schemas.HistoricalFigureDetail:
    """
    Return full details for a single historical figure.

    Args:
        slug: URL-safe unique identifier for the figure.
        db: Figures database session.

    Raises:
        HTTPException: 404 if the figure does not exist.

    Returns:
        Complete figure details, including any linked context entries.
    """
    figure = crud.get_figure_by_slug(db, slug=slug)
    if not figure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Figure not found")
    return figure
