"""
Main FastAPI application entry point for Places in Time History Chat.

This module configures the API, static frontend, CORS, startup tasks, and
provides a health endpoint that verifies configuration and RAG availability.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import Base as ChatBase
from app.database import SQLALCHEMY_DATABASE_URL as CHAT_DB_URL
from app.database import engine as chat_engine
from app.database import get_db_chat
from app.figures_database import FigureBase
from app.figures_database import SQLALCHEMY_DATABASE_URL as FIGURES_DB_URL
from app.figures_database import engine as figures_engine
from app.routers import admin, ask, auth, chat, figures, guest
from app.settings import get_settings
from app.utils.security import get_current_user


_settings = get_settings()
app = FastAPI(redirect_slashes=True)

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static_frontend"


def _allowed_origins() -> List[str]:
    """
    Resolve allowed CORS origins from centralized settings.

    Returns
    -------
    list[str]
        List of allowed origins.
    """
    return _settings.allowed_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(figures.router)
app.include_router(ask.router)
app.include_router(guest.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup() -> None:
    """
    Initialize databases and perform idempotent figures ingest.

    This ensures that required tables exist in both databases and runs the
    figures CSV ingestion when the seed changes.
    """
    _ = models
    ChatBase.metadata.create_all(bind=chat_engine)
    FigureBase.metadata.create_all(bind=figures_engine)
    from app.startup_ingest import maybe_ingest_seed_csv

    maybe_ingest_seed_csv(None)


@app.get("/health")
def health() -> JSONResponse:
    """
    Return a configuration and dependency health report.

    Returns
    -------
    fastapi.responses.JSONResponse
        Health status payload including RAG availability.
    """
    keys_present = {
        "OPENAI_API_KEY": bool(_settings.openai_api_key),
        "OPENROUTER_API_KEY": bool(_settings.openrouter_api_key),
    }
    rag_status = {"enabled": _settings.rag_enabled, "ok": False, "detail": None}
    try:
        if _settings.rag_enabled:
            from app.vector.chroma_client import get_figure_context_collection

            collection = get_figure_context_collection()
            _ = collection.name
            rag_status["ok"] = True
    except Exception as exc:
        rag_status["ok"] = False
        rag_status["detail"] = str(exc)

    payload = {
        "ok": True,
        "chat_db_url": CHAT_DB_URL,
        "figures_db_url": FIGURES_DB_URL,
        "keys_present": keys_present,
        "rag": rag_status,
        "debug": {"guest_prompt_debug": _settings.guest_prompt_debug},
    }
    return JSONResponse(payload)


@app.get(
    "/threads/user/{user_id}",
    response_model=List[schemas.ThreadRead],
)
def list_user_threads(
    user_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return all threads for the authenticated user.

    Parameters
    ----------
    user_id : int
        Target user identifier.
    db : sqlalchemy.orm.Session
        Database session dependency.
    current_user : app.models.User
        Authenticated user model.

    Returns
    -------
    list[app.schemas.ThreadRead]
        List of thread records for the user.
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access these threads")
    return crud.get_threads_by_user(db, user_id)


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    """
    Serve the landing page HTML.

    Returns
    -------
    fastapi.responses.FileResponse
        HTML file response.
    """
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/user/{user_id}/threads", response_class=FileResponse)
def serve_threads_page(user_id: int) -> FileResponse:
    """
    Serve the threads page HTML for a user.

    Parameters
    ----------
    user_id : int
        User identifier.

    Returns
    -------
    fastapi.responses.FileResponse
        HTML file response.
    """
    return FileResponse(STATIC_DIR / "threads.html", media_type="text/html")


@app.get("/guest/{slug}", response_class=FileResponse)
def serve_guest_page(slug: str) -> FileResponse:
    """
    Serve the guest chat page for a specific figure slug.

    Parameters
    ----------
    slug : str
        Historical figure slug.

    Returns
    -------
    fastapi.responses.FileResponse
        HTML file response.
    """
    return FileResponse(STATIC_DIR / "guest.html", media_type="text/html")


@app.get("/ui/figures", response_class=FileResponse)
def serve_figures_ui() -> FileResponse:
    """
    Serve a UI page listing figures that link to Ask.

    Returns
    -------
    fastapi.responses.FileResponse
        HTML file response.
    """
    return FileResponse(STATIC_DIR / "figures.html", media_type="text/html")


@app.get("/main.js", response_class=FileResponse)
def serve_main_js() -> FileResponse:
    """
    Serve main.js from static_frontend for legacy paths.

    Returns
    -------
    fastapi.responses.FileResponse
        JavaScript file response.
    """
    return FileResponse(STATIC_DIR / "main.js", media_type="application/javascript")


@app.get("/style.css", response_class=FileResponse)
def serve_style_css() -> FileResponse:
    """
    Serve style.css from static_frontend for legacy paths.

    Returns
    -------
    fastapi.responses.FileResponse
        CSS file response.
    """
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@app.get("/logo.png", response_class=FileResponse)
def serve_logo_png() -> FileResponse:
    """
    Serve logo.png from static_frontend for legacy paths.

    Returns
    -------
    fastapi.responses.FileResponse
        PNG image file response.
    """
    return FileResponse(STATIC_DIR / "logo.png", media_type="image/png")


@app.get("/threads_visual.png", response_class=FileResponse)
def serve_threads_visual() -> FileResponse:
    """
    Serve threads_visual.png from static_frontend for legacy paths.

    Returns
    -------
    fastapi.responses.FileResponse
        PNG image file response.
    """
    return FileResponse(STATIC_DIR / "threads_visual.png", media_type="image/png")


@app.get("/favicon.ico")
def serve_favicon_ico() -> Response:
    """
    Serve a stable favicon, preferring ICO, then app icon PNG.

    Returns
    -------
    fastapi.responses.Response
        ICO or PNG favicon response, or 404.
    """
    candidates = [
        STATIC_DIR / "pit-favicon-mark.ico",
        STATIC_DIR / "favicon.ico",
        STATIC_DIR / "icon-192.png",
    ]
    for p in candidates:
        if p.exists():
            media = "image/x-icon" if p.suffix == ".ico" else "image/png"
            return FileResponse(p, media_type=media)
    return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.get("/favicon.svg")
def serve_favicon_svg() -> Response:
    """
    Serve the SVG favicon if present.

    Returns
    -------
    fastapi.responses.Response
        SVG favicon response, or 404.
    """
    svg_path = STATIC_DIR / "favicon.svg"
    if svg_path.exists():
        return FileResponse(svg_path, media_type="image/svg+xml")
    return Response(status_code=status.HTTP_404_NOT_FOUND)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
