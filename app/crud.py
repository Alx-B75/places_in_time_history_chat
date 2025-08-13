"""CRUD operations for users, chats, threads, and historical figures."""

from sqlalchemy.orm import Session, selectinload

from app import models, schemas


# === User Functions ===

def get_user_by_username(db: Session, username: str) -> models.User | None:
    """Look up and return a user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> models.User | None:
    """Look up and return a user by ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user in the database."""
    db_user = models.User(
        username=user.username,
        hashed_password=user.hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# === Chat Functions ===

def get_all_chats(db: Session, limit: int = 100) -> list[models.Chat]:
    """Return the most recent chat messages."""
    return (
        db.query(models.Chat)
        .order_by(models.Chat.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_messages_by_user(db: Session, user_id: int, limit: int = 50) -> list[
    models.Chat]:
    """Retrieve all messages for a user, ordered by timestamp ascending."""
    return (
        db.query(models.Chat)
        .filter(models.Chat.user_id == user_id)
        .order_by(models.Chat.timestamp.asc())
        .limit(limit)
        .all()
    )


def get_messages_by_thread(db: Session, thread_id: int, limit: int = 50) -> list[
    models.Chat]:
    """Retrieve all messages in a specific thread."""
    return (
        db.query(models.Chat)
        .filter(models.Chat.thread_id == thread_id)
        .order_by(models.Chat.timestamp.asc())
        .limit(limit)
        .all()
    )


def create_chat_message(db: Session, chat: schemas.ChatMessageCreate) -> models.Chat:
    """Create a new message entry in the conversation."""
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


# === Thread Functions ===

def get_thread_by_id(db: Session, thread_id: int) -> models.Thread | None:
    """Retrieve a thread by ID."""
    return db.query(models.Thread).filter(models.Thread.id == thread_id).first()


def get_threads_by_user(db: Session, user_id: int) -> list[models.Thread]:
    """Retrieve all threads belonging to a user, ordered by newest first."""
    return (
        db.query(models.Thread)
        .filter(models.Thread.user_id == user_id)
        .order_by(models.Thread.created_at.desc())
        .all()
    )


def create_thread(db: Session, thread: schemas.ThreadCreate) -> models.Thread:
    """Create a new thread for a user."""
    db_thread = models.Thread(
        user_id=thread.user_id,
        title=thread.title,
        figure_slug=thread.figure_slug,
    )
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread


# === Historical Figure Functions ===

def get_all_figures(db: Session, skip: int = 0, limit: int = 100) -> list[
    models.HistoricalFigure]:
    """Retrieve all historical figures (with optional pagination)."""
    return (
        db.query(models.HistoricalFigure)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_figure_by_slug(db: Session, slug: str) -> models.HistoricalFigure | None:
    """Retrieve a figure by slug, including related context entries."""
    return (
        db.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == slug)
        .options(selectinload(models.HistoricalFigure.contexts))
        .first()
    )
