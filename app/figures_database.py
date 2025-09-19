"""Database setup for historical figures and vector context storage."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_figures_db_path() -> Path:
    return _repo_root() / "data" / "figures.db"


def _resolve_figures_db_path() -> Path:
    """
    Resolve the figures database path from the environment, Render /data mount,
    or fallback to the repo-local data directory.
    """
    env_path = os.getenv("FIGURES_DB_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        data_mount = Path("/data")
        if data_mount.exists() and os.access(data_mount, os.W_OK):
            path = data_mount / "figures.db"
        else:
            path = _default_figures_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


SQLALCHEMY_DATABASE_URL = f"sqlite:///{_resolve_figures_db_path()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

FigureSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

FigureBase = declarative_base()
