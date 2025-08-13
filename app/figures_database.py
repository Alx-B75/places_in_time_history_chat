"""Database setup for historical figures and vector context storage."""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Base directory setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# --- Path to figures.db ---
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'figures.db')}"

# --- SQLAlchemy Engine and Session Configuration ---
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

FigureSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

FigureBase = declarative_base()
