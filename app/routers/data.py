"""
Data download routes for exporting application artifacts.
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["Data"])


def _resolve_data_dir() -> str:
    """
    Resolves the directory containing data assets.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_dir = os.path.join(base_dir, "data")
    return os.getenv("DATA_DIR", default_dir)


@router.get("/download_db")
def download_figures_db() -> FileResponse:
    """
    Streams the figures database file as an attachment.
    """
    data_dir = _resolve_data_dir()
    db_path = os.path.join(data_dir, "figures.db")
    if not os.path.isfile(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename="figures.db",
    )
