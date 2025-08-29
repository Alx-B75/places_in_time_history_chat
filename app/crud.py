"""CRUD operations for users, chats, threads, guest data, and historical figures.

This module provides database helpers used across the application. It includes
user, chat, and thread CRUD, as well as figure listing/search and two distinct
helpers for figure text:

- get_figure_description: returns human-readable bio text for display
  (figure_contexts.bio -> long_bio -> short_summary -> fallback).
- get_figure_persona: returns only the persona prompt for system messages.

Both helpers intentionally keep persona and bio separate to avoid cross-contamination
between UI descriptions and prompt personas.
"""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """
    Return the user with the given username.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    username : str
        Username or email stored as username.

    Returns
    -------
    app.models.User | None
        User instance if found, otherwise None.
    """
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """
    Return the user with the given id.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    user_id : int
        Target user id.

    Returns
    -------
    app.models.User | None
        User instance if found, otherwise None.
    """
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """
    Create and persist a new user.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    user : app.schemas.UserCreate
        Validated user payload with hashed password.

    Returns
    -------
    app.models.User
        Newly created user.
    """
    db_user = models.User(username=user.username, hashed_password=user.hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_all_chats(db: Session, limit: int = 100) -> List[models.Chat]:
    """
    Return the most recent chats, newest first.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    limit : int
        Maximum rows to return.

    Returns
    -------
    list[app.models.Chat]
        Chat rows ordered by timestamp desc.
    """
    return (
        db.query(models.Chat)
        .order_by(models.Chat.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_messages_by_user(db: Session, user_id: int, limit: int = 50) -> List[models.Chat]:
    """
    Return messages for a user, oldest first.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    user_id : int
        Owner id.
    limit : int
        Maximum rows to return.

    Returns
    -------
    list[app.models.Chat]
        Chat rows ordered by timestamp asc.
    """
    return (
        db.query(models.Chat)
        .filter(models.Chat.user_id == user_id)
        .order_by(models.Chat.timestamp.asc())
        .limit(limit)
        .all()
    )


def get_messages_by_thread(db: Session, thread_id: int, limit: int = 50) -> List[models.Chat]:
    """
    Return messages for a thread, oldest first.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    thread_id : int
        Thread id.
    limit : int
        Maximum rows to return.

    Returns
    -------
    list[app.models.Chat]
        Chat rows ordered by timestamp asc.
    """
    return (
        db.query(models.Chat)
        .filter(models.Chat.thread_id == thread_id)
        .order_by(models.Chat.timestamp.asc())
        .limit(limit)
        .all()
    )


def create_chat_message(db: Session, chat: schemas.ChatMessageCreate) -> models.Chat:
    """
    Create and persist a chat message.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    chat : app.schemas.ChatMessageCreate
        Message payload.

    Returns
    -------
    app.models.Chat
        Newly created message.
    """
    db_chat = models.Chat(
        user_id=chat.user_id,
        role=chat.role,
        message=chat.message,
        model_used=chat.model_used,
        source_page=chat.source_page,
        thread_id=chat.thread_id,
        summary_of=chat.summary_of,
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat


def get_thread_by_id(db: Session, thread_id: int) -> Optional[models.Thread]:
    """
    Return a thread by id.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    thread_id : int
        Target thread id.

    Returns
    -------
    app.models.Thread | None
        Thread instance if found, otherwise None.
    """
    return db.query(models.Thread).filter(models.Thread.id == thread_id).first()


def get_threads_by_user(db: Session, user_id: int) -> List[models.Thread]:
    """
    Return all threads for a user, newest first.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    user_id : int
        Owner id.

    Returns
    -------
    list[app.models.Thread]
        Threads ordered by created_at desc.
    """
    return (
        db.query(models.Thread)
        .filter(models.Thread.user_id == user_id)
        .order_by(models.Thread.created_at.desc())
        .all()
    )


def create_thread(db: Session, thread: schemas.ThreadCreate) -> models.Thread:
    """
    Create and persist a new thread.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Chat database session.
    thread : app.schemas.ThreadCreate
        Thread payload.

    Returns
    -------
    app.models.Thread
        Newly created thread.
    """
    db_thread = models.Thread(
        user_id=thread.user_id,
        title=thread.title,
        figure_slug=thread.figure_slug,
    )
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread


def get_all_figures(db: Session, skip: int = 0, limit: int = 100) -> List[models.HistoricalFigure]:
    """
    Return historical figures with optional pagination.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Figures database session.
    skip : int
        Number of records to skip.
    limit : int
        Maximum number of records to return.

    Returns
    -------
    list[app.models.HistoricalFigure]
        Figure rows.
    """
    return db.query(models.HistoricalFigure).offset(skip).limit(limit).all()


def get_figure_by_slug(db: Session, slug: str) -> Optional[models.HistoricalFigure]:
    """
    Return a figure by slug with contexts preloaded.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Figures database session.
    slug : str
        Figure slug.

    Returns
    -------
    app.models.HistoricalFigure | None
        Figure instance if found, otherwise None.
    """
    return (
        db.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == slug)
        .options(selectinload(models.HistoricalFigure.contexts))
        .first()
    )


def get_figure_description(db: Session, slug: str) -> str:
    """
    Return descriptive bio text for a figure.

    Priority
    --------
    1) figure_contexts.content where content_type = 'bio'
    2) historical_figures.long_bio
    3) historical_figures.short_summary
    4) Fallback string derived from identity

    Notes
    -----
    This function intentionally never returns the persona prompt. It is meant
    for human-readable UI descriptions and summaries.
    """
    row = db.execute(
        text(
            """
            SELECT content
            FROM figure_contexts
            WHERE figure_slug = :slug
              AND content_type = 'bio'
            ORDER BY id ASC
            LIMIT 1
            """
        ),
        {"slug": slug},
    ).fetchone()
    if row and row[0]:
        desc = str(row[0]).strip()
        if desc:
            return desc

    row = db.execute(
        text(
            """
            SELECT long_bio, short_summary, name
            FROM historical_figures
            WHERE slug = :slug
            LIMIT 1
            """
        ),
        {"slug": slug},
    ).fetchone()
    if row:
        long_bio = (row[0] or "").strip()
        short_summary = (row[1] or "").strip()
        name = (row[2] or "").strip()

        if long_bio:
            return long_bio
        if short_summary:
            return short_summary
        if name:
            return f"About {name} ({slug})"

    return f"About {slug}"


def get_figure_persona(db: Session, slug: str) -> str:
    """
    Return the persona prompt text for a figure.

    Priority
    --------
    1) historical_figures.persona_prompt
    2) Empty string if not set

    Notes
    -----
    This function intentionally does not mix in bio text. It is used to supply
    a system persona for chat completions.
    """
    row = db.execute(
        text(
            """
            SELECT persona_prompt
            FROM historical_figures
            WHERE slug = :slug
            LIMIT 1
            """
        ),
        {"slug": slug},
    ).fetchone()
    if row and row[0]:
        val = str(row[0]).strip()
        if val:
            return val
    return ""


def search_figures(db: Session, query: str, limit: int = 20) -> List[models.HistoricalFigure]:
    """
    Return up to `limit` figures matching the query by name or slug.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Figures database session.
    query : str
        Case-insensitive substring to match in name or slug.
    limit : int
        Maximum rows to return.

    Returns
    -------
    list[app.models.HistoricalFigure]
        Matching figures ordered by name.
    """
    q = f"%{query.strip()}%"
    return (
        db.query(models.HistoricalFigure)
        .filter(or_(models.HistoricalFigure.name.ilike(q), models.HistoricalFigure.slug.ilike(q)))
        .order_by(models.HistoricalFigure.name.asc())
        .limit(limit)
        .all()
    )
