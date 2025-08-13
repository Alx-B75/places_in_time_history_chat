"""Main FastAPI application entry point for Places in Time History Chat."""

import os
from typing import List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.routers import auth, ask, chat, figures
from app.routers import data as data_router
from app.utils.security import get_current_user

load_dotenv()

app = FastAPI(redirect_slashes=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static_frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://places-in-time-chatbot.onrender.com",
        "http://localhost:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ask.router)
app.include_router(chat.router)
app.include_router(figures.router)
app.include_router(data_router.router)


@app.get("/health")
def health() -> JSONResponse:
    """
    Simple health check endpoint.
    """
    return JSONResponse({"ok": True})


@app.get("/threads/user/{user_id}", response_model=List[schemas.ThreadRead])
def list_user_threads(
    user_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return all threads for the authenticated user.
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access these threads")
    return crud.get_threads_by_user(db, user_id)


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    """
    Serve the landing page.
    """
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/user/{user_id}/threads", response_class=FileResponse)
def get_user_threads_page(user_id: int) -> FileResponse:
    """
    Serve the threads page for a user.
    """
    return FileResponse(os.path.join(STATIC_DIR, "threads.html"), media_type="text/html")


@app.get("/thread/{thread_id}", response_class=HTMLResponse)
def view_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db_chat),
) -> HTMLResponse:
    """
    Serve a simple HTML representation of a thread and its messages.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    messages = crud.get_messages_by_thread(db, thread_id)
    return HTMLResponse(f"<h1>Thread {thread_id}</h1><pre>{messages}</pre>")
