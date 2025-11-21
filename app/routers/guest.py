"""
Guest trial chat router.

This router enables an anonymous, short-lived guest chat experience scoped
to a specific historical figure. Guests can later upgrade their session to
a real user thread, migrating the transcript.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
import time
from typing import Any, Dict, Generator, List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from app.services.llm_client import LlmClient
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.settings import get_settings
from app.utils.prompt import build_prompt
from app.utils.security import get_current_user

router = APIRouter(prefix="/guest", tags=["Guest"])

_settings = get_settings()
llm_client = LlmClient()


_GUEST_RATE: Dict[str, List[float]] = {}
_GUEST_START_LIMIT = 10
_GUEST_WINDOW_SECONDS = 3600
_GUEST_ASK_LIMIT = 60
_GUEST_ASK_WINDOW_SECONDS = 3600


def _check_guest_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Simple in-memory rate limit for guest endpoints.

    Raises HTTPException(429) if the number of requests from ``key``
    within the last ``window_seconds`` exceeds ``limit``.
    """

    now = time.time()
    window_start = now - window_seconds
    bucket = _GUEST_RATE.setdefault(key, [])
    # prune old timestamps
    bucket[:] = [ts for ts in bucket if ts >= window_start]
    if len(bucket) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    bucket.append(now)


def get_figure_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session bound to the figures database.

    Yields
    ------
    sqlalchemy.orm.Session
        Database session for the figures database.
    """
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


class GuestStartResponse(BaseModel):
    """
    Response payload returned when starting a guest session.
    """

    session_started: bool
    figure_slug: str
    max_questions: int
    expires_at: Optional[datetime] = None


class GuestAskRequest(BaseModel):
    """Request payload for submitting a guest question."""
    message: str
    model_used: Optional[str] = None
    source_page: Optional[str] = None


class GuestAskResponse(BaseModel):
    """
    Response payload for a guest assistant answer.
    """

    answer: str
    sources: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None
    remaining_questions: int
    max_questions: int


class GuestUpgradeResponse(BaseModel):
    """
    Response payload returned after upgrading a guest session.
    """

    upgraded: bool
    user_id: int
    thread_id: int
    transferred_messages: int


def _get_limits() -> Dict[str, Any]:
    """
    Return server-side limits and settings for guest sessions.

    Returns
    -------
    dict
        Limit configuration for guest session lifetime and quotas.
    """
    max_q = 3
    ttl_minutes = 120
    secure_cookie = True
    return {
        "max_questions": max_q,
        "ttl": timedelta(minutes=ttl_minutes),
        "secure_cookie": secure_cookie,
    }


def _set_guest_cookie(response: Response, token: str, ttl: timedelta, secure_cookie: bool) -> None:
    """
    Set the HttpOnly cookie that identifies the guest session.

    Parameters
    ----------
    response : fastapi.Response
        Response instance to set the cookie on.
    token : str
        Session token value.
    ttl : datetime.timedelta
        Time-to-live for the cookie.
    secure_cookie : bool
        Whether to set the cookie with the Secure flag.
    """
    # Use SameSite=None to ensure the cookie is sent on cross-site XHR/fetch requests
    # from the static frontend domain to the API domain.
    response.set_cookie(
        key="guest_session",
        value=token,
        httponly=True,
        samesite="none",
        secure=secure_cookie,
        max_age=int(ttl.total_seconds()),
        path="/",
    )


@router.post("/start/{figure_slug}", response_model=GuestStartResponse)
def start_guest_session(
    figure_slug: str,
    response: Response,
    request: Request,
    db: Session = Depends(get_db_chat),
    figure_db: Session = Depends(get_figure_db),
) -> GuestStartResponse:
    """
    Create a new guest session for a given figure and set the session cookie.

    Parameters
    ----------
    figure_slug : str
        Target figure slug for the guest session.
    response : fastapi.Response
        Response instance to set cookies on.
    db : sqlalchemy.orm.Session
        Chat database session.
    figure_db : sqlalchemy.orm.Session
        Figures database session.

    Returns
    -------
    GuestStartResponse
        Details of the created session, including expiration.
    """
    limits = _get_limits()
    client_ip = request.client.host if request.client else "unknown"
    key = f"start:{client_ip}"
    _check_guest_rate_limit(key, _GUEST_START_LIMIT, _GUEST_WINDOW_SECONDS)
    figure = crud.get_figure_by_slug(figure_db, slug=figure_slug)
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + limits["ttl"]
    session = models.GuestSession(
        session_token=token,
        figure_slug=figure_slug,
        question_count=0,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    _set_guest_cookie(response, token, limits["ttl"], limits["secure_cookie"])
    return GuestStartResponse(
        session_started=True,
        figure_slug=figure_slug,
        max_questions=limits["max_questions"],
        expires_at=expires_at,
    )


@router.post("/ask", response_model=GuestAskResponse)
def guest_ask(
    payload: GuestAskRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db_chat),
    figure_db: Session = Depends(get_figure_db),
    guest_token: Optional[str] = Cookie(default=None, alias="guest_session"),
) -> GuestAskResponse:
    """
    Accept a guest question, enforce limits, and return an assistant answer.

    Parameters
    ----------
    payload : GuestAskRequest
        Guest message payload and options.
    response : fastapi.Response
        Response instance for any cookie updates.
    db : sqlalchemy.orm.Session
        Chat database session.
    figure_db : sqlalchemy.orm.Session
        Figures database session.
    guest_token : str | None
        Guest session cookie value.

    Returns
    -------
    GuestAskResponse
        Assistant answer, sources, usage, and remaining quota.
    """
    if not guest_token:
        raise HTTPException(status_code=400, detail="Guest session not found")
    client_ip = request.client.host if request.client else "unknown"
    key = f"ask:{client_ip}"
    _check_guest_rate_limit(key, _GUEST_ASK_LIMIT, _GUEST_ASK_WINDOW_SECONDS)
    limits = _get_limits()
    session = (
        db.query(models.GuestSession)
        .filter(models.GuestSession.session_token == guest_token)
        .first()
    )
    if not session:
        raise HTTPException(status_code=400, detail="Invalid guest session")
    if session.expires_at and session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Guest session expired")
    if session.question_count >= limits["max_questions"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guest question limit reached")

    figure = (
        figure_db.query(models.HistoricalFigure)
        .options(selectinload(models.HistoricalFigure.contexts))
        .filter(models.HistoricalFigure.slug == session.figure_slug)
        .first()
    )
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found for this session")

    history_before = (
        db.query(models.GuestMessage)
        .filter(models.GuestMessage.session_id == session.id)
        .order_by(models.GuestMessage.id.asc())
        .all()
    )
    history_dicts = [{"role": m.role, "message": m.message} for m in history_before]

    messages, sources = build_prompt(
        figure=figure,
        user_message=payload.message,
        thread_history=history_dicts,
        max_context_chars=4000,
        use_rag=_settings.rag_enabled,
        debug=_settings.guest_prompt_debug,
    )

    from app.config.llm_config import llm_config
    model_name = payload.model_used or llm_config.model
    resp = llm_client.generate(messages=messages, model=model_name, temperature=llm_config.temperature)
    answer = resp["choices"][0]["message"]["content"].strip() if resp.get("choices") else ""
    usage = resp.get("usage", {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    })

    db.add(models.GuestMessage(session_id=session.id, role="user", message=payload.message, model_used=model_name))
    db.add(models.GuestMessage(session_id=session.id, role="assistant", message=answer, model_used=model_name))
    session.question_count += 1
    db.commit()

    remaining = max(0, limits["max_questions"] - session.question_count)
    return GuestAskResponse(
        answer=answer,
        sources=sources,
        usage=usage,
        remaining_questions=remaining,
        max_questions=limits["max_questions"],
    )


@router.post("/upgrade", response_model=GuestUpgradeResponse)
def upgrade_guest_session(
    response: Response,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
    guest_token: Optional[str] = Cookie(default=None, alias="guest_session"),
) -> GuestUpgradeResponse:
    """
    Transfer a guest transcript into a real user thread and invalidate the session.

    Parameters
    ----------
    response : fastapi.Response
        Response instance to clear cookies on completion.
    db : sqlalchemy.orm.Session
        Chat database session.
    current_user : app.models.User
        Authenticated user.
    guest_token : str | None
        Guest session cookie value.

    Returns
    -------
    GuestUpgradeResponse
        Migration details including transferred message count.
    """
    if not guest_token:
        raise HTTPException(status_code=400, detail="Guest session not found")
    session = (
        db.query(models.GuestSession)
        .filter(models.GuestSession.session_token == guest_token)
        .first()
    )
    if not session:
        raise HTTPException(status_code=400, detail="Invalid guest session")

    title = f"Guest chat with {session.figure_slug or 'figure'}"
    thread_schema = schemas.ThreadCreate(
        user_id=current_user.id,
        title=title,
        figure_slug=session.figure_slug,
    )
    thread = crud.create_thread(db, thread_schema)

    messages = (
        db.query(models.GuestMessage)
        .filter(models.GuestMessage.session_id == session.id)
        .order_by(models.GuestMessage.id.asc())
        .all()
    )
    for m in messages:
        chat_schema = schemas.ChatMessageCreate(
            user_id=current_user.id,
            role=m.role,
            message=m.message,
            model_used=m.model_used,
            source_page=None,
            thread_id=thread.id,
            summary_of=None,
        )
        crud.create_chat_message(db, chat_schema)

    db.query(models.GuestMessage).filter(models.GuestMessage.session_id == session.id).delete()
    db.delete(session)
    # Create or update ThreadMeta to grant allowance for unverified users
    meta = db.query(models.ThreadMeta).filter(models.ThreadMeta.thread_id == thread.id).first()
    if meta is None:
        meta = models.ThreadMeta(thread_id=thread.id, origin="guest_upgrade", unverified_allowance_remaining=5)
        db.add(meta)
    else:
        meta.origin = "guest_upgrade"
        meta.unverified_allowance_remaining = 5
        db.add(meta)
    db.commit()

    response.delete_cookie("guest_session", path="/")
    return GuestUpgradeResponse(
        upgraded=True,
        user_id=current_user.id,
        thread_id=thread.id,
        transferred_messages=len(messages),
    )
