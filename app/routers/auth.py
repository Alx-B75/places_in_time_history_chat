"""Authentication routes for login and registration with typed validation."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db_chat
from app.routers.deps import get_credentials
from app.utils.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login_for_access_token(
    credentials: schemas.Credentials = Depends(get_credentials),
    db: Session = Depends(get_db_chat),
) -> dict:
    """Authenticate a user and return a JWT access token and identity."""
    user = crud.get_user_by_username(db, username=credentials.username)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )

    return {
        "user_id": user.id,
        "username": user.username,
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/register")
async def register_user(
    credentials: schemas.Credentials = Depends(get_credentials),
    db: Session = Depends(get_db_chat),
) -> dict:
    """Register a new user and return a JWT access token with identity data."""
    existing_user = crud.get_user_by_username(db, username=credentials.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = hash_password(credentials.password)
    user_schema = schemas.UserCreate(
        username=credentials.username,
        hashed_password=hashed_pw,
    )
    user = crud.create_user(db, user_schema)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )

    return {
        "user_id": user.id,
        "username": user.username,
        "access_token": access_token,
        "token_type": "bearer",
    }
