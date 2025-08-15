"""Main FastAPI application entry point for Places in Time History Chat.

Serves the API and static frontend with explicit routes for index and
user threads pages, plus compatibility routes for legacy asset paths.
"""

import os
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.routers import auth, ask, chat, figures
from app.utils.security import get_current_user, oauth2_scheme, ALGORITHM, SECRET_KEY

load_dotenv()

app = FastAPI(redirect_slashes=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static_frontend")

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


@app.get("/debug/token")
def debug_token(token: str = Depends(oauth2_scheme)) -> dict:
    """Debug endpoint to inspect the raw token and decoded payload."""
    from jose import jwt

    decoded = None
    error = None
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as exc:
        error = str(exc)

    return {
        "raw_token": token,
        "decoded_payload": decoded,
        "error": error,
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
