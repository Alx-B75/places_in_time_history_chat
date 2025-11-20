"""
Threaded chat routes and message completions using the unified prompt pipeline.
"""

from __future__ import annotations

from typing import Dict, Generator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import RedirectResponse
from app.services.llm_client import LlmClient
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.settings import get_settings
from app.utils.prompt import build_prompt
from app.utils.security import get_current_user


router = APIRouter(tags=["Chat"])

_settings = get_settings()
llm_client = LlmClient()


class ThreadCreatePayload(BaseModel):
    """Request body for creating a new conversation thread.

    The legacy user_id field is optional and used only for mismatch
    detection; the authenticated user always owns the thread.
    """

    user_id: Optional[int] = Field(default=None)
    title: Optional[str] = None
    figure_slug: Optional[str] = None
    age_profile: Optional[str] = None


class ThreadTitleUpdate(BaseModel):
    """
    Request body for updating a thread title.
    """

    title: str = Field(..., min_length=1, max_length=200)


class ThreadFigureUpdate(BaseModel):
    """
    Request body for updating or clearing a thread's historical figure.
    """

    figure_slug: Optional[str] = Field(default=None)


class FavoriteToggle(BaseModel):
    figure_slug: str


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
    current_user: models.User = Depends(get_current_user),
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
    # Enforce that the thread is always owned by the authenticated user.
    # For backward compatibility, validate any provided user_id matches when present.
    if payload.user_id is not None and payload.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create thread for another user",
        )
    title = payload.title or "New thread"
    # Normalize slug input (optional)
    fig_slug = (payload.figure_slug or "").strip() or None
    thread_in = schemas.ThreadCreate(user_id=current_user.id, title=title, figure_slug=fig_slug, age_profile=payload.age_profile)
    thread = crud.create_thread(db, thread_in)
    return {"thread_id": thread.id, "user_id": thread.user_id, "title": thread.title, "figure_slug": thread.figure_slug}


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


@router.delete("/threads/{thread_id}", status_code=204)
def delete_thread(
    thread_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Delete a thread owned by the current user.

    Parameters
    ----------
    thread_id : int
        Target thread id.
    db : sqlalchemy.orm.Session
        Chat database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    None
        Returns no content on success.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this thread")
    # Deletion cascades will remove associated chats due to relationship config.
    db.delete(thread)
    db.commit()


@router.post("/complete", response_class=RedirectResponse)
def chat_complete(
    request: Request,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    user_id: int = Form(...),
    message: str = Form(...),
    thread_id: Optional[int] = Form(None),
    figure_slug: Optional[str] = Form(None),
    current_user: models.User = Depends(get_current_user),
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
        user_id: Optional[int] = Form(default=None),
        Optional figure slug from the form.

    Returns
    -------
    fastapi.responses.RedirectResponse
        Redirect to the threads page for the user.
    """
    # Enforce that the operation is performed as the authenticated user.
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to act as another user")
    user = current_user

    if thread_id is None:
        initial_slug = (figure_slug or "").strip() or None
        if initial_slug:
            figure_obj = crud.get_figure_by_slug(db_fig, initial_slug)
    user_id : Optional[int]
                raise HTTPException(status_code=404, detail="Figure not found")
            initial_slug = figure_obj.slug
        thread_in = schemas.ThreadCreate(user_id=current_user.id, title="New thread", figure_slug=initial_slug)
        thread = crud.create_thread(db, thread_in)
        thread_id = thread.id
    else:
        thread = crud.get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if thread.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this thread")
        update_slug = (figure_slug or "").strip()
        if update_slug or figure_slug == "":
    # Enforce that the operation is performed as the authenticated user.
    # If a legacy user_id is supplied and does not match, forbid.
    if user_id is not None and user_id != current_user.id:
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

    # Attempt to retrieve age_profile from thread if present; default to 'general'
    age_profile = getattr(thread, "age_profile", None) or "general"

    messages, _sources = build_prompt(
        figure=figure,
        user_message=message,
        thread_history=history_dicts,
        max_context_chars=4000,
        use_rag=_settings.rag_enabled,
        debug=_settings.guest_prompt_debug,
        age_profile=age_profile,
    )

    user_msg = schemas.ChatMessageCreate(user_id=current_user.id, role="user", message=message, thread_id=thread_id)
    crud.create_chat_message(db, user_msg)

    from app.config.llm_config import llm_config
    response = llm_client.generate(
        messages=messages,
        model=llm_config.model,
        temperature=llm_config.temperature,
    )
    answer = response["choices"][0]["message"]["content"].strip() if response.get("choices") else ""

    assistant_msg = schemas.ChatMessageCreate(user_id=current_user.id, role="assistant", message=answer, thread_id=thread_id)
    saved = crud.create_chat_message(db, assistant_msg)
    # Persist sources used for this assistant response
    try:
        import json as _json
        saved.sources_json = _json.dumps(_sources or [])
        db.add(saved)
        db.commit()
        db.refresh(saved)
    except Exception:
        db.rollback()

    return RedirectResponse(url=f"/user/{current_user.id}/threads", status_code=status.HTTP_303_SEE_OTHER)


# --- User Favorites (alternative stable path) ---
@router.get("/user/favorites", response_model=List[schemas.FavoriteRead])
def list_user_favorites(
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    # Defensive normalization of id to handle SQLAlchemy instrumentation during testing
    user_id = getattr(current_user, 'id', None)
    if hasattr(user_id, 'expression'):
        user_id = current_user.__dict__.get('id', None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return crud.get_favorites_by_user(db, int(user_id))


@router.post("/user/favorites/{figure_slug}", response_model=schemas.FavoriteRead, status_code=status.HTTP_201_CREATED)
def add_user_favorite(
    figure_slug: str,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    current_user: models.User = Depends(get_current_user),
):
    # ensure figure exists
    if not crud.get_figure_by_slug(db_fig, slug=figure_slug):
        raise HTTPException(status_code=404, detail="Figure not found")
    user_id = getattr(current_user, 'id', None)
    if hasattr(user_id, 'expression'):
        user_id = current_user.__dict__.get('id', None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return crud.add_favorite(db, int(user_id), figure_slug)


@router.delete("/user/favorites/{figure_slug}", status_code=204)
def remove_user_favorite(
    figure_slug: str,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    user_id = getattr(current_user, 'id', None)
    if hasattr(user_id, 'expression'):
        user_id = current_user.__dict__.get('id', None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    ok = crud.remove_favorite(db, int(user_id), figure_slug)
    if not ok:
        raise HTTPException(status_code=404, detail="Favorite not found")
