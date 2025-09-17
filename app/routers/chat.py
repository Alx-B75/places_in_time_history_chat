"""Router for handling threaded chat interactions, thread management, and message completions.

This module provides endpoints to create, list, and update threads; fetch messages;
assign a historical figure to a thread; and process chat completions using an LLM.
It composes prompts using persona text and instruction-type contexts stored in the
figures database.
"""

import os
from typing import Any, Dict, Generator, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import RedirectResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.security import get_current_user

router = APIRouter(tags=["Chat"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ThreadCreatePayload(BaseModel):
    """Request body for creating a new conversation thread."""
    user_id: int = Field(...)
    title: Optional[str] = None


class ThreadTitleUpdate(BaseModel):
    """Request body for updating a thread title."""
    title: str = Field(..., min_length=1, max_length=200)


class ThreadFigureUpdate(BaseModel):
    """Request body for updating a thread's linked historical figure.

    If figure_slug is null or an empty string, the figure association is cleared.
    """
    figure_slug: Optional[str] = Field(default=None)


def get_figure_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the figures database."""
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_instruction_text(figure) -> str:
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
        ctype = (getattr(ctx, "content_type", "") or "").strip().lower()
        if ctype in labels:
            text = (getattr(ctx, "content", "") or "").strip()
            if text:
                blocks.append(text)
    return "\n\n".join(blocks).strip()


def build_system_prompt(figure, db_instructions: str = "") -> str:
    """
    Create a system prompt based on an assigned figure and DB-stored instructions.

    Parameters
    ----------
    figure : app.models.HistoricalFigure | None
        Figure instance associated with the thread.
    db_instructions : str
        Instruction text retrieved from figure contexts.

    Returns
    -------
    str
        Composed system prompt string.
    """
    if figure and getattr(figure, "persona_prompt", None):
        base = figure.persona_prompt
    elif figure:
        base = (
            f"You are {figure.name}, a historical figure. "
            "Answer clearly, accurately, and concisely. "
            "State uncertainty when appropriate."
        )
    else:
        base = (
            "You are a helpful and accurate historical guide. "
            "Answer clearly and concisely. State uncertainty when necessary."
        )
    db_instructions = (db_instructions or "").strip()
    if db_instructions:
        return f"{base}\n\n{db_instructions}"
    return base


def compact_context(
    contexts: List[Dict[str, Any]],
    max_chars: int = 4000,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Compact a list of context entries into a text block within a character budget.

    Parameters
    ----------
    contexts : list[dict]
        Context records for the figure.
    max_chars : int
        Character budget for the compacted context text.

    Returns
    -------
    tuple[str, list[dict]]
        The compacted context text and a list of source descriptors.
    """
    if not contexts:
        return "", []
    lines: List[str] = []
    sources: List[Dict[str, Any]] = []
    used = 0
    for c in contexts:
        src = c.get("source_name") or "source"
        url = c.get("source_url")
        text = (c.get("content") or "").strip()
        if not text:
            continue
        block = f"[{src}] {text}"
        if used + len(block) > max_chars and lines:
            break
        lines.append(block)
        used += len(block)
        sources.append({"source_name": src, "source_url": url})
    return "\n\n".join(lines), sources


def figure_context_payload(figure) -> List[Dict[str, Any]]:
    """
    Convert a figure's contexts ORM collection to a list of dictionaries.

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


@router.post("/threads", status_code=201)
def create_thread(
    payload: ThreadCreatePayload,
    db: Session = Depends(get_db_chat),
) -> dict:
    """
    Create a new thread for the user and return its identity.

    Parameters
    ----------
    payload : ThreadCreatePayload
        Thread creation data.
    db : sqlalchemy.orm.Session
        Chat database session.

    Returns
    -------
    dict
        Thread identity payload.
    """
    user = crud.get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    title = payload.title or "New thread"
    thread_in = schemas.ThreadCreate(
        user_id=payload.user_id,
        title=title,
        figure_slug=None,
    )
    thread = crud.create_thread(db, thread_in)
    return {"thread_id": thread.id, "user_id": thread.user_id, "title": thread.title}


@router.get("/threads/{thread_id}", response_model=schemas.ThreadRead)
def get_thread(
    thread_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ThreadRead:
    """
    Return a single thread if owned by the current user.

    Parameters
    ----------
    thread_id : int
        Thread identifier.
    db : sqlalchemy.orm.Session
        Chat database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    app.schemas.ThreadRead
        Thread record.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")
    return thread


@router.patch("/threads/{thread_id}/title", response_model=schemas.ThreadRead)
def update_thread_title(
    thread_id: int,
    payload: ThreadTitleUpdate,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ThreadRead:
    """
    Update the title of a thread owned by the current user.

    Parameters
    ----------
    thread_id : int
        Thread identifier.
    payload : ThreadTitleUpdate
        New title payload.
    db : sqlalchemy.orm.Session
        Chat database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    app.schemas.ThreadRead
        Updated thread record.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this thread")
    thread.title = payload.title
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.patch("/threads/{thread_id}/figure", response_model=schemas.ThreadRead)
def update_thread_figure(
    thread_id: int,
    payload: ThreadFigureUpdate,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ThreadRead:
    """
    Set or clear the historical figure on a thread owned by the current user.

    Parameters
    ----------
    thread_id : int
        Thread identifier.
    payload : ThreadFigureUpdate
        Figure slug payload.
    db : sqlalchemy.orm.Session
        Chat database session.
    db_fig : sqlalchemy.orm.Session
        Figures database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    app.schemas.ThreadRead
        Updated thread record.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this thread")

    slug = (payload.figure_slug or "").strip()
    if slug:
        figure = crud.get_figure_by_slug(db_fig, slug)
        if not figure:
            raise HTTPException(status_code=404, detail="Figure not found")
        thread.figure_slug = figure.slug
    else:
        thread.figure_slug = None

    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/threads/{thread_id}/messages", response_model=List[schemas.ChatMessageRead])
def get_thread_messages(
    thread_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.ChatMessageRead]:
    """
    Return all messages in a thread if the current user owns it.

    Parameters
    ----------
    thread_id : int
        Thread identifier.
    db : sqlalchemy.orm.Session
        Chat database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    list[app.schemas.ChatMessageRead]
        Ordered list of messages in the thread.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")
    return crud.get_messages_by_thread(db, thread_id, limit=1000)


@router.post("/complete", response_class=RedirectResponse)
def chat_complete(
    request: Request,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    user_id: int = Form(...),
    message: str = Form(...),
    thread_id: Optional[int] = Form(None),
) -> RedirectResponse:
    """
    Persist a user message, generate an assistant reply, and redirect to the threads page.

    If the thread has an assigned historical figure, the completion uses a persona
    system prompt and compacted context derived from that figure.

    Parameters
    ----------
    request : fastapi.Request
        Incoming HTTP request.
    db : sqlalchemy.orm.Session
        Chat database session.
    db_fig : sqlalchemy.orm.Session
        Figures database session.
    user_id : int
        Identifier of the user sending the message.
    message : str
        Message content.
    thread_id : int | None
        Optional thread identifier.

    Returns
    -------
    fastapi.responses.RedirectResponse
        Redirect to the threads page for the user.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if thread_id is None:
        thread_in = schemas.ThreadCreate(user_id=user_id, title="New thread", figure_slug=None)
        thread = crud.create_thread(db, thread_in)
        thread_id = thread.id
    else:
        thread = crud.get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if thread.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this thread")

    user_msg = schemas.ChatMessageCreate(
        user_id=user_id,
        role="user",
        message=message,
        thread_id=thread_id,
    )
    crud.create_chat_message(db, user_msg)

    history = crud.get_messages_by_thread(db, thread_id, limit=1000)

    figure = None
    if thread.figure_slug:
        figure = crud.get_figure_by_slug(db_fig, thread.figure_slug)

    instruction_text = _extract_instruction_text(figure)
    system_prompt = build_system_prompt(figure, instruction_text)
    contexts = figure_context_payload(figure) if figure else []
    ctx_text, _sources = compact_context(contexts, max_chars=4000)

    formatted_messages = [{"role": "system", "content": system_prompt}]
    if ctx_text:
        formatted_messages.append(
            {"role": "system", "content": f"Context for reference:\n{ctx_text}"}
        )
    formatted_messages += [{"role": m.role, "content": m.message} for m in history]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=formatted_messages,
        temperature=0.5,
    )
    answer = response.choices[0].message.content.strip()

    assistant_msg = schemas.ChatMessageCreate(
        user_id=user_id,
        role="assistant",
        message=answer,
        thread_id=thread_id,
    )
    crud.create_chat_message(db, assistant_msg)

    return RedirectResponse(
        url=f"/user/{user_id}/threads",
        status_code=status.HTTP_303_SEE_OTHER,
    )
