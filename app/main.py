"""Main FastAPI application entry point for Places in Time History Chat.

This module serves the API and static frontend. It includes explicit routes
for the landing page and the user threads page, a guest page route that
renders the guest chat client at `/guest/{slug}`, convenience routes for
legacy asset paths, robust favicon handling, and a static mount for other
assets under `/static`.
"""

import os
from pathlib import Path
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.routers import ask, auth, chat, figures, guest
from app.utils.security import get_current_user

load_dotenv()

app = FastAPI(redirect_slashes=True)

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static_frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "https://places-in-time-chatbot.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(figures.router)
app.include_router(ask.router)
app.include_router(guest.router)


@app.get("/health")
def health() -> JSONResponse:
    """Return a simple health check payload."""
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
    """Return all threads for the authenticated user."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access these threads",
        )
    return crud.get_threads_by_user(db, user_id)


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    """Serve the landing page HTML."""
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/user/{user_id}/threads", response_class=FileResponse)
def serve_threads_page(user_id: int) -> FileResponse:
    """Serve the threads page HTML for a user."""
    return FileResponse(STATIC_DIR / "threads.html", media_type="text/html")


@app.get("/guest/{slug}", response_class=FileResponse)
def serve_guest_page(slug: str) -> FileResponse:
    """Serve the guest chat page for a specific figure slug."""
    return FileResponse(STATIC_DIR / "guest.html", media_type="text/html")


@app.get("/ui/figures", response_class=FileResponse)
def serve_figures_ui() -> FileResponse:
    """Serve a UI page listing figures that link to Ask."""
    return FileResponse(STATIC_DIR / "figures.html", media_type="text/html")


@app.get("/main.js", response_class=FileResponse)
def serve_main_js() -> FileResponse:
    """Serve main.js from static_frontend for legacy paths."""
    return FileResponse(STATIC_DIR / "main.js", media_type="application/javascript")


@app.get("/style.css", response_class=FileResponse)
def serve_style_css() -> FileResponse:
    """Serve style.css from static_frontend for legacy paths."""
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@app.get("/logo.png", response_class=FileResponse)
def serve_logo_png() -> FileResponse:
    """Serve logo.png from static_frontend for legacy paths."""
    return FileResponse(STATIC_DIR / "logo.png", media_type="image/png")


@app.get("/threads_visual.png", response_class=FileResponse)
def serve_threads_visual() -> FileResponse:
    """Serve threads_visual.png from static_frontend for legacy paths."""
    return FileResponse(STATIC_DIR / "threads_visual.png", media_type="image/png")


@app.get("/favicon.ico")
def serve_favicon_ico() -> Response:
    """Serve a stable favicon, preferring ICO, then app icon PNG."""
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
    """Serve the SVG favicon if present, otherwise 404."""
    svg_path = STATIC_DIR / "favicon.svg"
    if svg_path.exists():
        return FileResponse(svg_path, media_type="image/svg+xml")
    return Response(status_code=status.HTTP_404_NOT_FOUND)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
