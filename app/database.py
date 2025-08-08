"""Database setup for the main chat history and user authentication system."""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Define path for SQLite database (Render-compatible) ---
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'chat_history.db')}"

# --- SQLAlchemy Engine and Session Configuration ---
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

# --- FastAPI Dependency for Database Session ---
def get_db_chat():
    """Yields a SQLAlchemy database session for use in dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
