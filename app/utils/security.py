"""
Security utilities for password hashing and JWT-based authentication, including admin step-up.

- Uses bcrypt_sha256 for new password hashes (solves bcrypt 72-byte limit; robust with latest bcrypt wheels).
- Still verifies legacy bcrypt hashes for existing users.
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

# Accept legacy "bcrypt" hashes, generate "bcrypt_sha256" going forward.
_pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    default="bcrypt_sha256",
    deprecated="auto",
)

_settings = get_settings()

_ALGORITHM = "HS256"
_ADMIN_STEPUP_TTL_MINUTES = 20

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
_oauth2_admin_scheme = OAuth2PasswordBearer(tokenUrl="/auth/admin/stepup")


def hash_password(password: str) -> str:
    """
    Return a secure hash for the given plain-text password.
    Uses bcrypt_sha256 to avoid the 72-byte bcrypt limit.
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Return True if the plain-text password matches the stored hash.
    Supports both bcrypt_sha256 and legacy bcrypt hashes.
    """
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, *, minutes: Optional[int] = None, scope: str = "user") -> str:
    """
    Create and sign a JWT access token with an expiration claim and scope.
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
    """
    return jwt.decode(token, _settings.secret_key, algorithms=[_ALGORITHM])


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(database.get_db_chat),
) -> models.User:
    """
    Return the authenticated user derived from a normal bearer token.
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


from typing import Optional
import os
from fastapi import Header, HTTPException, status

def admin_required(authorization: Optional[str] = Header(None)) -> str:
    """
    Validate admin access. Allows a local-dev bypass when ENVIRONMENT=dev.
    In production, requires a static bearer token matching ADMIN_TOKEN.
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()
    if env == "dev":
        return "dev-admin"
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if expected and authorization == f"Bearer {expected}":
        return "admin"
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
