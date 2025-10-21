"""
Authentication routes for login, registration, and admin step-up.
"""

from __future__ import annotations

import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db_chat
from app.routers.deps import get_credentials
from app.settings import get_settings
from app.utils.security import (
    create_access_token,
    hash_password,
    verify_password,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

_settings = get_settings()


class RegistrationRequest(BaseModel):
    """
    Payload for user registration with strong validation.
    """

    email: EmailStr
    password: str = Field(min_length=8)
    gdpr_consent: bool
    ai_ack: bool


class AdminStepUpRequest(BaseModel):
    """
    Payload for admin step-up containing password re-authentication.
    """

    password: str = Field(min_length=8)


def _validate_password_strength(password: str) -> None:
    """
    Enforce strong password discipline with mixed-case, digits, and symbols.

    Parameters
    ----------
    password : str
        Candidate password.

    Raises
    ------
    fastapi.HTTPException
        If the password does not meet the strength requirements.
    """
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must contain at least one special character.")


@router.post("/login")
async def login_for_access_token(
    credentials: schemas.Credentials = Depends(get_credentials),
    db: Session = Depends(get_db_chat),
) -> dict:
    """
    Authenticate a user and return a user-scoped JWT access token.
    """
    user = crud.get_user_by_username(db, username=credentials.username)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(
        data={"sub": user.username},
        minutes=_settings.access_token_expire_minutes,
        scope="user",
    )
    return {"user_id": user.id, "username": user.username, "access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def register_user(
    payload: RegistrationRequest,
    db: Session = Depends(get_db_chat),
) -> dict:
    """
    Register a new user and return a user-scoped JWT access token.
    """
    if not payload.gdpr_consent or not payload.ai_ack:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You must accept the GDPR consent and AI disclosure to register.")

    existing_user = crud.get_user_by_username(db, username=payload.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account already exists with this email address.")

    _validate_password_strength(payload.password)

    hashed_pw = hash_password(payload.password)
    user_schema = schemas.UserCreate(username=payload.email, hashed_password=hashed_pw)
    user = crud.create_user(db, user_schema)

    access_token = create_access_token(
        data={"sub": user.username},
        minutes=_settings.access_token_expire_minutes,
        scope="user",
    )
    return {"user_id": user.id, "username": user.username, "access_token": access_token, "token_type": "bearer"}



@router.post("/admin/stepup")
async def admin_stepup(
    payload: AdminStepUpRequest,
    db: Session = Depends(get_db_chat),
    current_user=Depends(get_current_user),
) -> dict:
    """
    Issue a short-lived admin-scoped JWT after re-authenticating the admin's password.

    Returns
    -------
    dict
        Admin access token and identity.
    """
    user = crud.get_user_by_username(db, username=current_user.username)
    if not user or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    admin_token = create_access_token(data={"sub": user.username}, scope="admin")
    return {"user_id": user.id, "username": user.username, "admin_access_token": admin_token, "token_type": "bearer"}
