"""
Authentication routes for login and registration with typed validation.
"""

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

router = APIRouter()


@router.post("/login", tags=["Auth"])
async def login_for_access_token(
    credentials: schemas.Credentials = Depends(get_credentials),
    db: Session = Depends(get_db_chat),
):
    """
    Authenticates a user with provided credentials and returns a JWT access token.

    The endpoint accepts both application/json and form-encoded payloads via the
    credentials dependency. On success, a bearer token and user identity data are
    returned for client-side storage and subsequent authorization.
    """
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


@router.post("/register", tags=["Auth"])
async def register_user(
    credentials: schemas.Credentials = Depends(get_credentials),
    db: Session = Depends(get_db_chat),
):
    """
    Registers a new user account and returns a JWT access token with identity data.

    The endpoint accepts both application/json and form-encoded payloads via the
    credentials dependency. If the username already exists, a 400 error is raised.
    """
    existing_user = crud.get_user_by_username(db, username=credentials.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = hash_password(credentials.password)
    user_schema = schemas.UserCreate(username=credentials.username, hashed_password=hashed_pw)
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
