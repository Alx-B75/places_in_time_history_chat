"""Guest trial chat router.

This router enables an anonymous, short-lived guest chat experience that is
scoped to a specific historical figure. The flow is:
1) Start a guest session for a figure, which sets an HttpOnly cookie.
2) Ask up to a server-enforced maximum number of questions in that session.
3) Upgrade the session by logging in or registering, which transfers the guest
   transcript into a real user thread and invalidates the guest session.

The implementation is isolated from authenticated chat routes and uses
dedicated guest tables, avoiding regression risks in existing flows.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.crud import create_chat_message, create_thread
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.security import get_current_user

router = APIRouter(prefix="/guest", tags=["Guest"])


def get_figure_db() -> Session:
    """Yield a SQLAlchemy session bound to the figures database."""
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


class GuestStartResponse(BaseModel):
    """Response payload returned when starting a guest session."""
    session_started: bool
    figure_slug: str
    max_questions: int
    expires_at: Optional[datetime] = None


class GuestAskRequest(BaseModel):
    """Request payload for submitting a guest question."""
    message: str
    model_used: Optional[str] = "gpt-4o-mini"
    source_page: Optional[str] = None


class GuestAskResponse(BaseModel):
    """Response payload for a guest assistant answer."""
    answer: str
    sources: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None
    remaining_questions: int
    max_questions: int


class GuestUpgradeResponse(BaseModel):
    """Response payload returned after upgrading a guest session."""
    upgraded: bool
    user_id: int
    thread_id: int
    transferred_messages: int


def _get_limits() -> Dict[str, Any]:
    """Return server-side limits and settings for guest sessions."""
    max_q = int(os.getenv("GUEST_MAX_QUESTIONS", "3"))
    ttl_minutes = int(os.getenv("GUEST_SESSION_TTL_MINUTES", "120"))
    secure_cookie = os.getenv("GUEST_COOKIE_SECURE", "true").lower() == "true"
    return {
        "max_questions": max_q,
        "ttl": timedelta(minutes=ttl_minutes),
        "secure_cookie": secure_cookie,
    }


def _set_guest_cookie(response: Response, token: str, ttl: timedelta, secure_cookie: bool) -> None:
    """Set the HttpOnly cookie that identifies the guest session."""
    response.set_cookie(
        key="guest_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        max_age=int(ttl.total_seconds()),
        path="/",
    )


def _build_system_prompt(figure: models.HistoricalFigure) -> str:
    """Compose a system prompt for the selected historical figure."""
    if getattr(figure, "persona_prompt", None):
        return figure.persona_prompt
    name = figure.name or "a historical figure"
    return (
        f"You are {name}. Answer concisely and accurately. "
        "If you are unsure, say so and explain what would be needed to answer."
    )


def _build_context_snippet(figure_db: Session, slug: str, char_budget: int = 2000) -> Dict[str, Any]:
    """Assemble a compact grounding context and source list for a figure."""
    figure = (
        figure_db.query(models.HistoricalFigure)
        .options(selectinload(models.HistoricalFigure.contexts))
        .filter(models.HistoricalFigure.slug == slug)
        .first()
    )
    if not figure:
        return {"text": "", "sources": []}
    text_parts: List[str] = []
    sources: List[Dict[str, Any]] = []
    used = 0
    for c in figure.contexts or []:
        snippet = (c.content or "").strip()
        if not snippet:
            continue
        take = snippet[: max(0, char_budget - used)]
        if not take:
            break
        text_parts.append(take)
        used += len(take)
        sources.append(
            {
                "source_name": c.source_name or "source",
                "source_url": c.source_url,
                "content_type": c.content_type,
            }
        )
        if used >= char_budget:
            break
    return {"text": "\n\n".join(text_parts), "sources": sources}


def _call_llm(system_prompt: str, user_message: str, context_text: str, model_name: str) -> Dict[str, Any]:
    """Call the language model to produce an assistant answer."""
    client = OpenAI()
    prompt = user_message
    if context_text:
        prompt = f"Context:\n{context_text}\n\nUser question:\n{user_message}"
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    answer = resp.choices[0].message.content if resp.choices else ""
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
        "completion_tokens": getattr(resp.usage, "completion_tokens", None),
        "total_tokens": getattr(resp.usage, "total_tokens", None),
    }
    return {"answer": answer or "", "usage": usage}


@router.post("/start/{figure_slug}", response_model=GuestStartResponse)
def start_guest_session(
    figure_slug: str,
    response: Response,
    db: Session = Depends(get_db_chat),
    figure_db: Session = Depends(get_figure_db),
) -> GuestStartResponse:
    """Create a new guest session for a given figure and set the session cookie."""
    limits = _get_limits()
    figure = (
        figure_db.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == figure_slug)
        .first()
    )
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
    db: Session = Depends(get_db_chat),
    figure_db: Session = Depends(get_figure_db),
    guest_token: Optional[str] = Cookie(default=None, alias="guest_session"),
) -> GuestAskResponse:
    """Accept a guest question, enforce limits, and return an assistant answer."""
    if not guest_token:
        raise HTTPException(status_code=400, detail="Guest session not found")
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest question limit reached",
        )
    figure = (
        figure_db.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == session.figure_slug)
        .first()
    )
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found for this session")
    db.add(
        models.GuestMessage(
            session_id=session.id,
            role="user",
            message=payload.message,
            model_used=payload.model_used,
        )
    )
    session.question_count += 1
    db.commit()
    system_prompt = _build_system_prompt(figure)
    context_info = _build_context_snippet(figure_db, figure.slug)
    llm_out = _call_llm(
        system_prompt,
        payload.message,
        context_info["text"],
        payload.model_used or "gpt-4o-mini",
    )
    answer = llm_out["answer"]
    db.add(
        models.GuestMessage(
            session_id=session.id,
            role="assistant",
            message=answer,
            model_used=payload.model_used,
        )
    )
    db.commit()
    remaining = max(0, limits["max_questions"] - session.question_count)
    return GuestAskResponse(
        answer=answer,
        sources=context_info["sources"],
        usage=llm_out.get("usage"),
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
    """Transfer a guest transcript into a real user thread and invalidate the session."""
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
    thread = create_thread(db, thread_schema)
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
        create_chat_message(db, chat_schema)
    db.query(models.GuestMessage).filter(models.GuestMessage.session_id == session.id).delete()
    db.delete(session)
    db.commit()
    response.delete_cookie("guest_session", path="/")
    return GuestUpgradeResponse(
        upgraded=True,
        user_id=current_user.id,
        thread_id=thread.id,
        transferred_messages=len(messages),
    )
