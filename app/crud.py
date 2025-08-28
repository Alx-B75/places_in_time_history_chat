"""CRUD operations for users, chats, threads, and historical figures."""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Return the user with the given username, or None."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """Return the user with the given id, or None."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create and return a new user."""
    db_user = models.User(username=user.username, hashed_password=user.hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_all_chats(db: Session, limit: int = 100) -> List[models.Chat]:
    """Return the most recent chat records, newest first."""
    return (
        db.query(models.Chat)
        .order_by(models.Chat.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_messages_by_user(db: Session, user_id: int, limit: int = 50) -> List[models.Chat]:
    """Return messages for a user, oldest first."""
    return (
        db.query(models.Chat)
        .filter(models.Chat.user_id == user_id)
        .order_by(models.Chat.timestamp.asc())
        .limit(limit)
        .all()
    )


def get_messages_by_thread(db: Session, thread_id: int, limit: int = 50) -> List[models.Chat]:
    """Return messages for a thread, oldest first."""
    return (
        db.query(models.Chat)
        .filter(models.Chat.thread_id == thread_id)
        .order_by(models.Chat.timestamp.asc())
        .limit(limit)
        .all()
    )


def create_chat_message(db: Session, chat: schemas.ChatMessageCreate) -> models.Chat:
    """Create and return a new chat message."""
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
    """Return the thread with the given id, or None."""
    return db.query(models.Thread).filter(models.Thread.id == thread_id).first()


def get_threads_by_user(db: Session, user_id: int) -> List[models.Thread]:
    """Return all threads for a user, newest first."""
    return (
        db.query(models.Thread)
        .filter(models.Thread.user_id == user_id)
        .order_by(models.Thread.created_at.desc())
        .all()
    )


def create_thread(db: Session, thread: schemas.ThreadCreate) -> models.Thread:
    """Create and return a new thread."""
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
    """Return historical figures with optional pagination."""
    return db.query(models.HistoricalFigure).offset(skip).limit(limit).all()


def get_figure_by_slug(db: Session, slug: str) -> Optional[models.HistoricalFigure]:
    """Return a figure by slug, with contexts preloaded."""
    return (
        db.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == slug)
        .options(selectinload(models.HistoricalFigure.contexts))
        .first()
    )


def get_figure_description(db, slug: str) -> str:
    """
    Return a description for a figure by slug.

    Prefers 'bio' in figure_contexts; falls back to historical_figures.persona_prompt.
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
        return str(row[0]).strip()

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
        return str(row[0]).strip()

    return ""


def search_figures(db: Session, query: str, limit: int = 20) -> List[models.HistoricalFigure]:
    """Return up to `limit` figures matching the query by name or slug."""
    q = f"%{query.strip()}%"
    return (
        db.query(models.HistoricalFigure)
        .filter(or_(models.HistoricalFigure.name.ilike(q), models.HistoricalFigure.slug.ilike(q)))
        .order_by(models.HistoricalFigure.name.asc())
        .limit(limit)
        .all()
    )
