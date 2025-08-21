"""Main FastAPI application entry point for Places in Time History Chat.

This module serves the API and static frontend with explicit routes for the
index and user threads pages, plus compatibility routes for legacy asset
paths. On startup, the application initializes both databases and performs a
lightweight, non-destructive migration for guest tables as needed.
"""

import os
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import Base, engine, get_db_chat
from app.figures_database import FigureBase, engine as figures_engine
from app.routers import ask, auth, chat, figures, guest
from app.utils.migrations import migrate_guest_tables
from app.utils.security import get_current_user

load_dotenv()

app = FastAPI(redirect_slashes=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static_frontend")


@app.on_event("startup")
def init_db() -> None:
    """Create tables and run a minimal guest-table migration on startup."""
    migrate_guest_tables(engine)
    Base.metadata.create_all(bind=engine)
    FigureBase.metadata.create_all(bind=figures_engine)


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


@app.get("/threads/user/{user_id}", response_model=List[schemas.ThreadRead])
def list_user_threads(
    user_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """Return all threads for the authenticated user."""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access these threads")
    return crud.get_threads_by_user(db, user_id)


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    """Serve the landing page HTML."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/user/{user_id}/threads", response_class=FileResponse)
def serve_threads_page(user_id: int) -> FileResponse:
    """Serve the threads page HTML for a user."""
    return FileResponse(os.path.join(STATIC_DIR, "threads.html"), media_type="text/html")


@app.get("/ui/figures", response_class=FileResponse)
def serve_figures_ui() -> FileResponse:
    """Serve the UI page that lists figures and links to Ask."""
    return FileResponse(os.path.join(STATIC_DIR, "figures.html"), media_type="text/html")


@app.get("/guest/{figure_slug}")
def serve_guest_ui(figure_slug: str) -> RedirectResponse:
    """Redirect pretty guest routes to the static guest page with a slug query.

    Using a redirect ensures the client always receives the slug via the query
    string, avoiding any ambiguity in client-side path parsing.
    """
    return RedirectResponse(url=f"/static/guest.html?slug={figure_slug}", status_code=307)


@app.get("/main.js", response_class=FileResponse)
def serve_main_js() -> FileResponse:
    """Serve main.js from static_frontend for legacy paths."""
    return FileResponse(os.path.join(STATIC_DIR, "main.js"), media_type="application/javascript")


@app.get("/style.css", response_class=FileResponse)
def serve_style_css() -> FileResponse:
    """Serve style.css from static_frontend for legacy paths."""
    return FileResponse(os.path.join(STATIC_DIR, "style.css"), media_type="text/css")


@app.get("/logo.png", response_class=FileResponse)
def serve_logo_png() -> FileResponse:
    """Serve logo.png from static_frontend for legacy paths."""
    return FileResponse(os.path.join(STATIC_DIR, "logo.png"), media_type="image/png")


@app.get("/threads_visual.png", response_class=FileResponse)
def serve_threads_visual() -> FileResponse:
    """Serve threads_visual.png from static_frontend for legacy paths."""
    return FileResponse(os.path.join(STATIC_DIR, "threads_visual.png"), media_type="image/png")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
