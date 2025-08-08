"""Database connection for the reference figures database (read-only)."""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Path for Render-compatible storage ---
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'figures.db')}"

# --- SQLAlchemy Engine and Session Configuration ---
engine_figure = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

FigureSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_figure,
)

FigureBase = declarative_base()
