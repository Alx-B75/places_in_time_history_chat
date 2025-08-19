"""Question-answering routes for historical figure chats, with guest trial support.

This endpoint supports both authenticated users and guest sessions:
- If authenticated, normal behavior applies (user_id required and enforced).
- If unauthenticated, the active GuestSession is resolved from the cookie,
  the request is allowed up to `max_messages`, and the thread is linked to
  the guest session. Once the trial cap is reached, the route returns:

    HTTP 403
    {
        "detail": {"code": "TRIAL_EXCEEDED", "remaining": 0}
    }

Frontend can catch this to trigger registration/login.
"""

import os
from typing import Any, Dict, Generator, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.security import get_current_user
from app.guest_utils import get_active_guest_session

router = APIRouter(tags=["Ask"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_figure_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the figures database."""
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_system_prompt(figure: Optional[models.HistoricalFigure]) -> str:
    """Return a system prompt using a figure’s persona if available."""
    if figure and getattr(figure, "persona_prompt", None):
        return figure.persona_prompt
    if figure:
        return (
            f"You are {figure.name}, a historical figure. "
            f"Answer clearly, accurately, and concisely for curious readers. "
            f"If something is uncertain or debated, state that explicitly."
        )
    return (
        "You are a helpful and accurate historical guide. "
        "Answer clearly and concisely. If a fact is uncertain, say so."
    )


def _compact_context(
    contexts: List[Dict[str, Any]], max_chars: int = 4000
) -> Tuple[str, List[Dict[str, Any]]]:
    """Compact context entries into a single string under a character budget and return sources."""
    if not contexts:
        return "", []
    pieces: List[str] = []
    sources: List[Dict[str, Any]] = []
    total = 0
    for c in contexts:
        src = c.get("source_name") or "source"
        url = c.get("source_url")
        text = c.get("content") or ""
        if not text:
            continue
        snippet = text.strip()
        if not snippet:
            continue
        block = f"[{src}] {snippet}"
        if total + len(block) > max_chars and pieces:
            break
        pieces.append(block)
        total += len(block)
        sources.append({"source_name": src, "source_url": url})
    return "\n\n".join(pieces), sources


def _figure_context_payload(figure) -> List[Dict[str, Any]]:
    """Convert a HistoricalFigure with .contexts into a list of plain dicts."""
    results: List[Dict[str, Any]] = []
    if not figure or not getattr(figure, "contexts", None):
        return results
    for ctx in figure.contexts:
        results.append(
            {
                "figure_slug": ctx.figure_slug,
                "source_name": ctx.source_name,
                "source_url": ctx.source_url,
                "content_type": ctx.content_type,
                "content": ctx.content,
                "is_manual": ctx.is_manual,
            }
        )
    return results


@router.post("/ask")
def ask(
    payload: schemas.AskRequest,
    request: Request,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    current_user: Optional[models.User] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Answer a user question (auth or guest), persist messages, and enforce trial limits.

    Authenticated:
        - Require `payload.user_id` to match `current_user.id`.
        - Enforce thread ownership for existing threads.

    Guest (unauthenticated):
        - Resolve active GuestSession from cookie.
        - Enforce `max_messages` limit. On exceed, return 403 with code TRIAL_EXCEEDED.
        - For new threads, create a thread with `user_id=None` and link to guest.
        - For existing threads, ensure they are guest-owned by this session.

    Returns a JSON payload with the assistant answer, sources, thread_id, and usage.
    """
    # Determine auth vs guest mode
    is_authed = current_user is not None

    # Validate figure (if provided)
    figure = None
    if payload.figure_slug:
        figure = crud.get_figure_by_slug(db_fig, payload.figure_slug)
        if not figure:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Figure not found")

    # Resolve or create thread
    thread = None
    if payload.thread_id is not None:
        thread = crud.get_thread_by_id(db, payload.thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    if is_authed:
        # Authenticated flow: enforce ownership
        if payload.user_id is None or payload.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        if thread is not None and thread.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        if thread is None:
            # Create a user-owned thread
            thread_in = schemas.ThreadCreate(
                user_id=current_user.id,
                title="Ask session",
                figure_slug=payload.figure_slug,
            )
            thread = crud.create_thread(db, thread_in)
    else:
        # Guest flow: resolve guest session and enforce trial cap
        guest = get_active_guest_session(request, db)
        if guest is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "GUEST_REQUIRED"},
            )
        if guest.message_count >= guest.max_messages:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "TRIAL_EXCEEDED", "remaining": 0},
            )
        # Thread constraints for guests
        if thread is not None:
            # Must be guest-owned by this session
            if thread.user_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "OWNERSHIP_MISMATCH"},
                )
            if thread.guest_session_id and thread.guest_session_id != guest.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "GUEST_SESSION_MISMATCH"},
                )
        else:
            # Create a guest-owned thread
            thread_in = schemas.ThreadCreate(
                user_id=None,
                title="Ask session",
                figure_slug=payload.figure_slug,
            )
            thread = crud.create_thread(db, thread_in)
            # Link it to the active guest session
            thread.guest_session_id = guest.id
            db.add(thread)
            db.commit()
            db.refresh(thread)
        # Count this guest message
        guest.message_count += 1
        db.add(guest)
        db.commit()

    # Persist the user message
    user_id_for_chat = current_user.id if is_authed else None
    user_msg = schemas.ChatMessageCreate(
        user_id=user_id_for_chat,
        role="user",
        message=payload.message,
        thread_id=thread.id,
        model_used=payload.model_used,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, user_msg)

    # Build system prompt and context
    system_prompt = _build_system_prompt(figure)
    contexts = _figure_context_payload(figure) if figure else []
    ctx_text, sources = _compact_context(contexts, max_chars=4000)

    # Chat history
    history = crud.get_messages_by_thread(db, thread.id, limit=1000)
    formatted = [{"role": "system", "content": system_prompt}]
    if ctx_text:
        formatted.append({"role": "system", "content": f"Context for reference:\n{ctx_text}"})
    for m in history:
        formatted.append({"role": m.role, "content": m.message})

    # LLM call
    model_name = payload.model_used or "gpt-4o-mini"
    response = client.chat.completions.create(
        model=model_name,
        messages=formatted,
        temperature=0.3,
    )
    answer = response.choices[0].message.content.strip() if response.choices else ""

    usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
        "total_tokens": getattr(response.usage, "total_tokens", 0),
    }

    # Persist assistant message
    assistant_msg = schemas.ChatMessageCreate(
        user_id=user_id_for_chat,
        role="assistant",
        message=answer,
        thread_id=thread.id,
        model_used=model_name,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, assistant_msg)

    return {
        "answer": answer,
        "sources": sources,
        "thread_id": thread.id,
        "usage": usage,
    }
