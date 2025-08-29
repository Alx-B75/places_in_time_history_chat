"""Database setup for the main chat history and user authentication system.

This module configures the primary SQLite database used for chat history,
authentication, and related entities. The database path can be overridden
via the CHAT_DB_PATH environment variable. If not provided, the default
path resolves to `<repo>/data/chat_history.db`.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _repo_root() -> Path:
    """
    Return the repository root directory based on this file location.

    Returns
    -------
    pathlib.Path
        Absolute path to the repository root.
    """
    return Path(__file__).resolve().parents[1]


def _default_chat_db_path() -> Path:
    """
    Compute the default chat database path under the repo's data directory.

    Returns
    -------
    pathlib.Path
        Absolute path to the default chat database.
    """
    return _repo_root() / "data" / "chat_history.db"


def _resolve_chat_db_path() -> Path:
    """
    Resolve the chat database path from the environment or use the default.

    Returns
    -------
    pathlib.Path
        Absolute database file path.
    """
    env_path = os.getenv("CHAT_DB_PATH")
    raw = env_path if env_path else str(_default_chat_db_path())
    path = Path(raw).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


SQLALCHEMY_DATABASE_URL = f"sqlite:///{_resolve_chat_db_path()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db_chat():
    """
    Provide a SQLAlchemy session for FastAPI dependency injection.

    Yields
    ------
    sqlalchemy.orm.Session
        Database session bound to the chat database.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
