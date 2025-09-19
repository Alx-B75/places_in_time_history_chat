"""
Security utilities for password hashing and JWT-based authentication, including admin step-up.

This module provides:
- Password hashing and verification.
- Normal user JWT creation and verification.
- Admin step-up JWT creation with a short TTL and scope claim.
- Dependency helpers for current user and admin-only access.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import crud, models, database
from app.settings import get_settings


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_settings = get_settings()

_ALGORITHM = "HS256"
_ADMIN_STEPUP_TTL_MINUTES = 20

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
_oauth2_admin_scheme = OAuth2PasswordBearer(tokenUrl="/auth/admin/stepup")


def hash_password(password: str) -> str:
    """
    Return a bcrypt hash for the given plain-text password.
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Return True if the plain-text password matches the stored hash.
    """
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, *, minutes: Optional[int] = None, scope: str = "user") -> str:
    """
    Create and sign a JWT access token with an expiration claim and scope.

    Parameters
    ----------
    data : dict
        Claims to include, must contain a stable subject identifier.
    minutes : int | None
        Expiration in minutes. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES for user scope
        and a short TTL for admin scope.
    scope : str
        Token scope, either "user" or "admin".

    Returns
    -------
    str
        Encoded JWT.
    """
    exp_minutes = minutes
    if exp_minutes is None:
        exp_minutes = _ADMIN_STEPUP_TTL_MINUTES if scope == "admin" else _settings.access_token_expire_minutes
    to_encode = data.copy()
    to_encode.update({"scope": scope})
    expire = datetime.now(timezone.utc) + timedelta(minutes=exp_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _settings.secret_key, algorithm=_ALGORITHM)


def _decode_token(token: str) -> dict:
    """
    Decode a JWT and return its payload.

    Parameters
    ----------
    token : str
        Encoded JWT.

    Returns
    -------
    dict
        Decoded claims.

    Raises
    ------
    jose.JWTError
        If decoding fails or the token is invalid.
    """
    return jwt.decode(token, _settings.secret_key, algorithms=[_ALGORITHM])


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(database.get_db_chat),
) -> models.User:
    """
    Return the authenticated user derived from a normal bearer token.

    Parameters
    ----------
    token : str
        Bearer token from the Authorization header.
    db : sqlalchemy.orm.Session
        Database session.

    Returns
    -------
    app.models.User
        The authenticated user.

    Raises
    ------
    fastapi.HTTPException
        If the token is invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = _decode_token(token)
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user


def admin_required(
    token: str = Depends(_oauth2_admin_scheme),
    db: Session = Depends(database.get_db_chat),
) -> models.User:
    """
    Validate an admin step-up token and return the admin user.

    Parameters
    ----------
    token : str
        Admin bearer token from the Authorization header.
    db : sqlalchemy.orm.Session
        Database session.

    Returns
    -------
    app.models.User
        The authenticated admin user.

    Raises
    ------
    fastapi.HTTPException
        If the token is invalid, not an admin scope, or the user lacks admin role.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = _decode_token(token)
        if payload.get("scope") != "admin":
            raise credentials_exception
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return user
