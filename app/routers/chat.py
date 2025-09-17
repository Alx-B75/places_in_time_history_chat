"""Router for handling threaded chat interactions, thread management, and message
completions using a unified prompt pipeline.

This module provides endpoints to create, list, and update threads; fetch messages;
assign a historical figure to a thread; and process chat completions. It composes
prompts via the centralized builder that merges persona, context, and thread history.
"""

import os
from typing import Any, Dict, Generator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import RedirectResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.prompt import build_prompt
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
    """Request body for updating or clearing a thread's historical figure."""
    figure_slug: Optional[str] = Field(default=None)


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
    figure_slug: Optional[str] = Form(None),
) -> RedirectResponse:
    """
    Persist a user message, generate an assistant reply, and redirect to the threads page.

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
    figure_slug : str | None
        Optional figure slug from the form.

    Returns
    -------
    fastapi.responses.RedirectResponse
        Redirect to the threads page for the user.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if thread_id is None:
        initial_slug = (figure_slug or "").strip() or None
        if initial_slug:
            figure_obj = crud.get_figure_by_slug(db_fig, initial_slug)
            if not figure_obj:
                raise HTTPException(status_code=404, detail="Figure not found")
            initial_slug = figure_obj.slug
        thread_in = schemas.ThreadCreate(
            user_id=user_id,
            title="New thread",
            figure_slug=initial_slug,
        )
        thread = crud.create_thread(db, thread_in)
        thread_id = thread.id
    else:
        thread = crud.get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if thread.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this thread")
        update_slug = (figure_slug or "").strip()
        if update_slug or figure_slug == "":
            if update_slug:
                figure_obj = crud.get_figure_by_slug(db_fig, update_slug)
                if not figure_obj:
                    raise HTTPException(status_code=404, detail="Figure not found")
                thread.figure_slug = figure_obj.slug
            else:
                thread.figure_slug = None
            db.add(thread)
            db.commit()
            db.refresh(thread)

    history_before = crud.get_messages_by_thread(db, thread_id, limit=1000)
    history_dicts = [{"role": m.role, "message": m.message} for m in history_before]

    figure = None
    if thread.figure_slug:
        figure = crud.get_figure_by_slug(db_fig, thread.figure_slug)

    messages, _sources = build_prompt(
        figure=figure,
        user_message=message,
        thread_history=history_dicts,
        max_context_chars=4000,
        use_rag=True,
    )

    user_msg = schemas.ChatMessageCreate(
        user_id=user_id,
        role="user",
        message=message,
        thread_id=thread_id,
    )
    crud.create_chat_message(db, user_msg)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
    )
    answer = response.choices[0].message.content.strip() if response.choices else ""

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
