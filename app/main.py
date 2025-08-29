"""Main FastAPI application entry point for Places in Time History Chat.

This module serves the API and static frontend. It includes explicit routes
for the landing page and the user threads page, a guest page route that
renders the guest chat client at `/guest/{slug}`, convenience routes for
legacy asset paths, robust favicon handling, and a static mount for other
assets under `/static`.

CORS origins are configurable via the ALLOWED_ORIGINS environment variable
as a comma-separated list. If not set, a sensible default is used for local
development and the Render static host.

On startup, the application logs the active database URLs and ensures that
database tables exist for both the primary chat database and the figures
database. It also performs an idempotent CSV ingestion for historical figures
when the seed CSV content has changed.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import uvicorn
from dotenv import load_dotenv
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
from app.utils.security import get_current_user

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("places-in-time")

app = FastAPI(redirect_slashes=True)

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static_frontend"


def _allowed_origins() -> List[str]:
    """
    Resolve allowed CORS origins.

    Reads ALLOWED_ORIGINS as a comma-separated list. If unset, defaults to
    localhost and the deployed static host used during development.

    Returns
    -------
    list[str]
        List of allowed origins.
    """
    raw = os.getenv("ALLOWED_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:8000",
        "https://places-in-time-chatbot.onrender.com",
        "https://places-in-time-history-chat.onrender.com",
    ]


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
    Initialize databases, log configuration details, and ingest figures CSV.

    This logs the active database URLs, ensures that required tables exist
    in both the chat and figures databases, and performs an idempotent
    CSV ingestion for historical figures when the seed CSV changes.
    """
    _ = models
    logger.info("Starting Places in Time service")
    logger.info("Chat DB URL: %s", CHAT_DB_URL)
    logger.info("Figures DB URL: %s", FIGURES_DB_URL)
    ChatBase.metadata.create_all(bind=chat_engine)
    FigureBase.metadata.create_all(bind=figures_engine)

    from app.startup_ingest import maybe_ingest_seed_csv

    ran, report = maybe_ingest_seed_csv(logger)
    if ran:
        logger.info("Figures ingest ran: %s", report)
    else:
        logger.info("Figures ingest skipped: %s", report)


@app.get("/health")
def health() -> JSONResponse:
    """
    Return a simple health check payload.

    Returns
    -------
    fastapi.responses.JSONResponse
        Health status payload.
    """
    return JSONResponse({"ok": True})


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

    Raises
    ------
    fastapi.HTTPException
        If the requester does not own the requested threads.
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access these threads",
        )
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
