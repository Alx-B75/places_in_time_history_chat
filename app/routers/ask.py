"""Question-answering routes for historical figure chats.

This module composes prompts using persona text and instruction-type contexts
stored in the figures database.
"""

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


def _extract_instruction_text(
    figure: Optional[models.HistoricalFigure],
) -> str:
    """
    Return concatenated instruction text from a figure's contexts.

    Instruction rows are detected by content_type in the set
    {"instruction", "instructions", "persona", "system"} case-insensitively.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        Figure instance with contexts preloaded.

    Returns
    -------
    str
        Concatenated instruction text or an empty string.
    """
    if not figure or not getattr(figure, "contexts", None):
        return ""
    labels = {"instruction", "instructions", "persona", "system"}
    blocks: List[str] = []
    for ctx in figure.contexts:
        ctype = (ctx.content_type or "").strip().lower()
        if ctype in labels:
            text = (ctx.content or "").strip()
            if text:
                blocks.append(text)
    return "\n\n".join(blocks).strip()


def _build_system_prompt(
    figure: Optional[models.HistoricalFigure],
    db_instructions: str = "",
) -> str:
    """
    Compose the system prompt from persona, fallback text, and DB instructions.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        The historical figure associated with the request.
    db_instructions : str
        Instruction text retrieved from figure contexts.

    Returns
    -------
    str
        The system prompt text to seed the assistant.
    """
    if figure and getattr(figure, "persona_prompt", None):
        base = figure.persona_prompt
    elif figure:
        base = (
            f"You are {figure.name}, a historical figure. "
            "Answer clearly, accurately, and concisely for curious readers. "
            "If something is uncertain or debated, state that explicitly."
        )
    else:
        base = (
            "You are a helpful and accurate historical guide. "
            "Answer clearly and concisely. If a fact is uncertain, say so."
        )
    db_instructions = (db_instructions or "").strip()
    if db_instructions:
        return f"{base}\n\n{db_instructions}"
    return base


def _compact_context(
    contexts: List[Dict[str, Any]],
    max_chars: int = 4000,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Compact context entries into a single string and return sources.

    Parameters
    ----------
    contexts : list[dict]
        List of context records for the figure.
    max_chars : int
        Character budget for the compacted context text.

    Returns
    -------
    tuple[str, list[dict]]
        The compacted context text and a list of source descriptors.
    """
    if not contexts:
        return "", []
    pieces: List[str] = []
    sources: List[Dict[str, Any]] = []
    total = 0
    for c in contexts:
        src = c.get("source_name") or "source"
        url = c.get("source_url")
        text = c.get("content") or ""
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


def _figure_context_payload(
    figure: Optional[models.HistoricalFigure],
) -> List[Dict[str, Any]]:
    """
    Convert a HistoricalFigure with contexts into a list of plain dicts.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        The historical figure instance.

    Returns
    -------
    list[dict]
        List of context dictionaries suitable for compaction.
    """
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
    """
    Answer a user question with optional figure context and persist messages.

    The associated figure is resolved with the following precedence:
    1) If a thread_id is supplied and the thread has a figure_slug, use that.
    2) Otherwise, if payload.figure_slug is provided, use that.
    3) Otherwise, no figure persona or context is applied.

    If no thread_id is provided, a new thread is created. When creating a new
    thread and a figure_slug is provided, the thread is initialized with that
    figure.
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
    instruction_text = _extract_instruction_text(figure)
    system_prompt = _build_system_prompt(figure, instruction_text)
    contexts = _figure_context_payload(figure) if figure else []
    ctx_text, sources = _compact_context(contexts, max_chars=4000)

    history = crud.get_messages_by_thread(db, thread.id, limit=1000)
    formatted = [{"role": "system", "content": system_prompt}]
    if ctx_text:
        formatted.append(
            {"role": "system", "content": f"Context for reference:\n{ctx_text}"}
        )
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
