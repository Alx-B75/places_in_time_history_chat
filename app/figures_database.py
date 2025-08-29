"""Database setup for historical figures and vector context storage.

This module configures the SQLite database used to store historical figures
metadata and any related context. The database path can be overridden via
the FIGURES_DB_PATH environment variable. If not provided, the default
path resolves to `<repo>/data/figures.db`.
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


def _default_figures_db_path() -> Path:
    """
    Compute the default figures database path under the repo's data directory.

    Returns
    -------
    pathlib.Path
        Absolute path to the default figures database.
    """
    return _repo_root() / "data" / "figures.db"


def _resolve_figures_db_path() -> Path:
    """
    Resolve the figures database path from the environment or use the default.

    Returns
    -------
    pathlib.Path
        Absolute database file path.
    """
    env_path = os.getenv("FIGURES_DB_PATH")
    raw = env_path if env_path else str(_default_figures_db_path())
    path = Path(raw).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


SQLALCHEMY_DATABASE_URL = f"sqlite:///{_resolve_figures_db_path()}"

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
