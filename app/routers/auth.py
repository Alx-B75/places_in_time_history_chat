"""Authentication router for login and registration."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()


@router.post("/login", tags=["Auth"])
async def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_chat),
):
    """Authenticate user and return access token."""
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


@router.post("/register", tags=["Auth"])
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db_chat),
):
    """Register a new user."""
    existing_user = crud.get_user_by_username(db, username=username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = hash_password(password)
    user_schema = schemas.UserCreate(username=username, hashed_password=hashed_pw)
    user = crud.create_user(db, user_schema)

    return {"message": f"User '{user.username}' created successfully"}
