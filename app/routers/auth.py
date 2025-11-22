"""
Authentication routes for login, registration, and admin step-up.
"""

from __future__ import annotations

import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse
import logging
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.database import get_db_chat
from app.routers.deps import get_credentials
from app.settings import get_settings
from app.utils.email_utils import send_email
from app.utils.email_verification import create_email_verification_token, verify_email_verification_token
from app.utils.security import (
    create_access_token,
    hash_password,
    verify_password,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
_log = logging.getLogger("auth")

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


class AdminLoginResponse(BaseModel):
    user_id: int
    username: str
    access_token: str
    admin_access_token: str
    token_type: str = "bearer"


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

    # Optional gate: require verified email for login when enabled
    if _settings.REQUIRE_VERIFIED_EMAIL_FOR_LOGIN:
        prof = db.query(models.UserProfile).filter(models.UserProfile.user_id == user.id).first()
        if not prof or not int(getattr(prof, "email_verified", 0)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email address not verified")

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

    # Create or update a UserProfile with email and mark unverified
    existing_profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user.id).first()
    if existing_profile is None:
        existing_email = db.query(models.UserProfile).filter(models.UserProfile.email == str(payload.email)).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        profile = models.UserProfile(user_id=user.id, email=str(payload.email), email_verified=0)
        db.add(profile)
    else:
        existing_profile.email = str(payload.email)
        existing_profile.email_verified = 0
        db.add(existing_profile)
    db.commit()

    # Issue verification token and send email (tests may monkeypatch send_email)
    token = None
    verify_url = None
    try:
        token = create_email_verification_token(user.id, str(payload.email), _settings)
        base = (_settings.FRONTEND_BASE_URL or "https://places-in-time-history-chat.onrender.com").rstrip("/")
        verify_url = f"{base}/auth/verify-email?token={token}"
        email_body = (
            "Welcome to Places in Time!\n\n"
            f"Please verify your email by clicking this link: {verify_url}\n\n"
            "If you did not sign up, you can safely ignore this email."
        )
        try:
            send_email(str(payload.email), "Verify your Places in Time account", email_body, settings=_settings)
        except RuntimeError as e:
            _log.warning("Verification email failed for %s: %s", payload.email, e)
    except Exception as e:
        _log.error("Unexpected failure preparing verification email for %s", payload.email, exc_info=True)
        # Surface a 500 so we do not hide systemic errors (token/signing issues)
        raise HTTPException(status_code=500, detail="Failed to prepare verification email")

    access_token = create_access_token(
        data={"sub": user.username},
        minutes=_settings.access_token_expire_minutes,
        scope="user",
    )
    return {
        "user_id": user.id,
        "username": user.username,
        "access_token": access_token,
        "token_type": "bearer",
        "email_verification_sent": bool(token),
        "verification_token": token,
        "verification_url": verify_url,
    }



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


@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(
    credentials: schemas.Credentials = Depends(get_credentials),
    db: Session = Depends(get_db_chat),
) -> AdminLoginResponse:
    """
    Admin-only login that issues both a user-scoped token and an admin-scoped token.

    This avoids exposing the generic user login flow in the Admin UI and ensures
    only admins can sign in to the dashboard.
    """
    user = crud.get_user_by_username(db, username=credentials.username)
    if not user or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    user_token = create_access_token(
        data={"sub": user.username},
        minutes=_settings.access_token_expire_minutes,
        scope="user",
    )
    admin_token = create_access_token(data={"sub": user.username}, scope="admin")
    return AdminLoginResponse(
        user_id=user.id,
        username=user.username,
        access_token=user_token,
        admin_access_token=admin_token,
    )


@router.get("/me")
async def auth_me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db_chat)) -> dict:
    """Return the current authenticated user's basic profile.

    This leverages the standard user-scoped bearer token produced by /auth/login or /auth/register.
    Response kept intentionally slim for dashboard header display.
    """
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    email = getattr(profile, "email", None)
    email_verified = int(getattr(profile, "email_verified", 0)) if profile else 0
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "role": getattr(current_user, "role", None),
        "email": email,
        "email_verified": email_verified,
    }

@router.post("/resend-verification")
async def resend_verification(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db_chat)) -> dict:
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
    if not profile or not getattr(profile, "email", None):
        raise HTTPException(status_code=400, detail="No email on profile")
    if int(getattr(profile, "email_verified", 0)) == 1:
        raise HTTPException(status_code=400, detail="Email already verified")
    try:
        token = create_email_verification_token(current_user.id, profile.email, _settings)
        base = (_settings.FRONTEND_BASE_URL or "https://places-in-time-history-chat.onrender.com").rstrip("/")
        verify_url = f"{base}/auth/verify-email?token={token}"
        body = (
            "Resend verification for Places in Time\n\n"
            f"Click to verify your email: {verify_url}\n\n"
            "If you did not request this, you can ignore it."
        )
        send_email(profile.email, "Resend: verify your Places in Time account", body, settings=_settings)
    except RuntimeError as e:
        _log.error("Resend verification failed for %s: %s", profile.email, e)
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    return {"detail": "Verification email sent"}


@router.get("/verify-email")
def verify_email(
    token: str,
    request: Request,
    db: Session = Depends(get_db_chat),
    settings = Depends(get_settings),
):
    """Verify a user's email from a signed token and mark email_verified=True.

    Content negotiation:
    - If Accept includes 'application/json' returns JSON.
    - If Accept includes 'text/html' returns an HTML page.
    - Default (no Accept) preserves legacy JSON behavior (tests rely on this).
    """
    accept = (request.headers.get("accept") or "").lower()
    wants_json = "application/json" in accept or ("text/html" not in accept and accept != "")
    _log.info("Email verification request received")
    try:
        user_id, email = verify_email_verification_token(token, settings)
    except Exception as e:
        _log.info("Email verification failure: %s", e)
        if wants_json:
            return {"status": "invalid or expired"}
        # Serve error HTML
        from pathlib import Path
        error_path = Path(__file__).resolve().parents[2] / "static_frontend" / "verify_error.html"
        return FileResponse(str(error_path), media_type="text/html")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        _log.info("Email verification failure: user not found")
        if wants_json:
            return {"status": "invalid or expired"}
        from pathlib import Path
        error_path = Path(__file__).resolve().parents[2] / "static_frontend" / "verify_error.html"
        return FileResponse(str(error_path), media_type="text/html")

    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user.id).first()
    if profile is None:
        profile = models.UserProfile(user_id=user.id, email=str(email), email_verified=1)
        db.add(profile)
    else:
        # Use setattr to avoid static type instrumentation complaints
        setattr(profile, "email", str(email))
        setattr(profile, "email_verified", 1)
        db.add(profile)
    db.commit()
    _log.info("Email verification success for user_id=%s", user_id)
    if wants_json:
        return {"status": "verified"}
    from pathlib import Path
    ok_path = Path(__file__).resolve().parents[2] / "static_frontend" / "verified.html"
    return FileResponse(str(ok_path), media_type="text/html")
