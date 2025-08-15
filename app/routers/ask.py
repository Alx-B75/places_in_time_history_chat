"""Question-answering routes for historical figure chats."""

import os
from typing import Any, Dict, Generator, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.security import get_current_user

router = APIRouter(tags=["Ask"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_figure_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the figures database."""
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_system_prompt(
    figure: Optional[models.HistoricalFigure],
) -> str:
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


def _compact_context(contexts: List[Dict[str, Any]], max_chars: int = 4000) -> Tuple[str, List[Dict[str, Any]]]:
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
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    current_user: models.User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Answer a user question with optional figure context, enforcing ownership and persisting messages."""
    if current_user.id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    thread = None
    if payload.thread_id is not None:
        thread = crud.get_thread_by_id(db, payload.thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        if thread.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    else:
        thread_in = schemas.ThreadCreate(
            user_id=current_user.id,
            title="Ask session",
            figure_slug=payload.figure_slug,
        )
        thread = crud.create_thread(db, thread_in)

    user_msg = schemas.ChatMessageCreate(
        user_id=current_user.id,
        role="user",
        message=payload.message,
        thread_id=thread.id,
        model_used=payload.model_used,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, user_msg)

    figure = None
    if payload.figure_slug:
        figure = crud.get_figure_by_slug(db_fig, payload.figure_slug)

    system_prompt = _build_system_prompt(figure)
    contexts = _figure_context_payload(figure) if figure else []
    ctx_text, sources = _compact_context(contexts, max_chars=4000)

    history = crud.get_messages_by_thread(db, thread.id, limit=1000)
    formatted = [{"role": "system", "content": system_prompt}]
    if ctx_text:
        formatted.append({"role": "system", "content": f"Context for reference:\n{ctx_text}"})
    for m in history:
        formatted.append({"role": m.role, "content": m.message})

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
