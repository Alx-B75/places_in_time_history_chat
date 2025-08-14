"""Main FastAPI application entry point for Places in Time History Chat.

Serves the API and static frontend with explicit routes for index and
user threads pages, plus compatibility routes for legacy asset paths.
"""

import os
from datetime import timedelta
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.routers import auth, ask, chat, figures
from app.utils.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

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
    """Simple health check endpoint."""
    return JSONResponse({"ok": True})


@app.post("/login")
async def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_chat),
):
    """Authenticate a user and return a JWT access token and identity."""
    user = crud.get_user_by_username(db, username=username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
    }


@app.post("/register")
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_chat),
):
    """Register a new user."""
    if crud.get_user_by_username(db, username=username):
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = hash_password(password)
    user_schema = schemas.UserCreate(username=username, hashed_password=hashed_pw)
    user = crud.create_user(db, user_schema)
    return {"message": f"User '{user.username}' created successfully", "user_id": user.id}


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


# Compatibility routes for legacy asset paths referenced by cached pages
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


# Serve all other static assets under /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
