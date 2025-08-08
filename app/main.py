"""Main FastAPI application entry point for Places in Time History Chat."""

import os
from datetime import timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn

from app import crud, models, schemas
from app.database import get_db_chat
from app.templating import templates
from app.figures_database import FigureSessionLocal
from app.utils.security import (
    verify_password,
    hash_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user,
)

# Routers
from app.routers import auth, ask, chat, figures

# Load environment variables
load_dotenv()

app = FastAPI()

# === CORS Setup ===
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

# === Auth Endpoints (Login + Register) ===

@app.post("/login")
async def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_chat),
):
    user = crud.get_user_by_username(db, username=username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=401,
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
    }


@app.post("/register")
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_chat),
):
    if crud.get_user_by_username(db, username=username):
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_pw = hash_password(password)
    user_schema = schemas.UserCreate(username=username, hashed_password=hashed_pw)
    user = crud.create_user(db, user_schema)

    return {"message": f"User '{user.username}' created successfully"}


# === Protected Threads Endpoint (API) ===

@app.get("/threads/user/{user_id}", response_model=List[schemas.ThreadRead])
def list_user_threads(
    user_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access these threads")
    return crud.get_threads_by_user(db, user_id)


# === HTML Page Endpoints ===

@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(os.path.join("static_frontend", "index.html"))


@app.get("/user/{user_id}/threads", response_class=FileResponse)
def get_user_threads_page(user_id: int):
    return FileResponse(os.path.join("static_frontend", "threads.html"))


@app.get("/thread/{thread_id}", response_class=HTMLResponse)
def view_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db_chat),
):
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    figure = None
    if thread.figure_slug:
        fig_db = FigureSessionLocal()
        try:
            figure = crud.get_figure_by_slug(fig_db, slug=thread.figure_slug)
        finally:
            fig_db.close()

    messages = crud.get_messages_by_thread(db, thread_id)

    return templates.TemplateResponse(
        "thread.html",
        {
            "request": request,
            "thread": thread,
            "messages": messages,
            "user_id": thread.user_id,
            "thread_id": thread.id,
            "figure": figure,
        },
    )


# === Include Routers ===

app.include_router(auth.router)
app.include_router(ask.router, prefix="/ask")
app.include_router(chat.router)
app.include_router(figures.router)


# === Static Frontend Mount ===

app.mount("/", StaticFiles(directory="static_frontend"), name="static")


# === Local Dev Entry Point ===

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
