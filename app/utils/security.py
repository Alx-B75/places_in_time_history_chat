"""
Security utilities for password hashing and JWT-based authentication, including admin step-up.

- Uses bcrypt_sha256 for new password hashes (solves bcrypt 72-byte limit; robust with latest bcrypt wheels).
- Still verifies legacy bcrypt hashes for existing users.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Header, Cookie
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


def get_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require that the authenticated user has role=admin.

    This enforces role-based access using normal user tokens.
    """
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


def get_current_user_loose(
    authorization: str | None = Header(None),
    pit_cookie: str | None = Cookie(None, alias="pit_access_token"),
    pit_admin_cookie: str | None = Cookie(None, alias="pit_admin_token"),
    alt_cookie: str | None = Cookie(None, alias="access_token"),
    db: Session = Depends(database.get_db_chat),
) -> models.User:
    """Authenticate using either a Bearer header or a host-scoped cookie.

    This is intended for static page GET routes where the browser performs a
    direct navigation without attaching the Authorization header, but the
    login/register script previously stored a non-httpOnly cookie.
    """
    token: str | None = None
    # Prefer explicit Bearer header
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    # Fall back to cookies set by the static frontend script
    if not token:
        token = pit_cookie or pit_admin_cookie or alt_cookie
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = _decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_admin_user_loose(current_user: models.User = Depends(get_current_user_loose)) -> models.User:
    """Like get_admin_user, but accepts either Bearer header or dev cookie token.

    Useful for static HTML GET routes where the browser doesn't attach the
    Authorization header automatically during navigation, but our dev login
    script has set a non-httpOnly cookie (pit_access_token).
    """
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user
