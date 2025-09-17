"""Question-answering routes for historical figure chats.

This module uses the unified prompt builder to compose messages with persona,
context, and thread history. It ensures consistent prompt construction across
the application.
"""

import os
from typing import Any, Dict, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.prompt import build_prompt
from app.utils.security import get_current_user

router = APIRouter(tags=["Ask"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


@router.post("/ask")
def ask(
    payload: schemas.AskRequest,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    current_user: models.User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Answer a user question with optional figure context and persist messages.

    The associated figure is resolved with the following precedence:
    1) If a thread_id is supplied and the thread has a figure_slug, use that.
    2) Otherwise, if payload.figure_slug is provided, use that.
    3) Otherwise, no figure persona or context is applied.

    If no thread_id is provided, a new thread is created. When creating a new
    thread and a figure_slug is provided, the thread is initialized with that
    figure.

    Parameters
    ----------
    payload : app.schemas.AskRequest
        Request payload including message and optional figure/thread data.
    db : sqlalchemy.orm.Session
        Chat database session.
    db_fig : sqlalchemy.orm.Session
        Figures database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    dict
        The answer, sources, thread_id, and usage metadata.
    """
    if current_user.id != payload.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    thread = None
    if payload.thread_id is not None:
        thread = crud.get_thread_by_id(db, payload.thread_id)
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found",
            )
        if thread.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized",
            )
    else:
        thread_in = schemas.ThreadCreate(
            user_id=current_user.id,
            title="Ask session",
            figure_slug=payload.figure_slug,
        )
        thread = crud.create_thread(db, thread_in)

    resolved_slug: Optional[str] = None
    if thread and getattr(thread, "figure_slug", None):
        resolved_slug = thread.figure_slug
    elif payload.figure_slug:
        resolved_slug = payload.figure_slug

    user_msg = schemas.ChatMessageCreate(
        user_id=current_user.id,
        role="user",
        message=payload.message,
        thread_id=thread.id,
        model_used=payload.model_used,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, user_msg)

    figure = crud.get_figure_by_slug(db_fig, resolved_slug) if resolved_slug else None
    history = crud.get_messages_by_thread(db, thread.id, limit=1000)
    history_dicts = [{"role": m.role, "message": m.message} for m in history]

    messages, sources = build_prompt(
        figure=figure,
        user_message=payload.message,
        thread_history=history_dicts,
        max_context_chars=4000,
        use_rag=True,
    )

    model_name = payload.model_used or "gpt-4o-mini"
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.3,
    )
    answer = response.choices[0].message.content.strip() if response.choices else ""

    usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
        "total_tokens": getattr(response.usage, "total_tokens", 0),
    }

    assistant_msg = schemas.ChatMessageCreate(
        user_id=current_user.id,
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
