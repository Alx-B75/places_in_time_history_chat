"""Lightweight migrations for guest tables with safe fallback recreate.

This module ensures the guest tables match the ORM models. It performs
non-destructive column/index additions when possible. If the primary key
definition on guest tables is incorrect, it safely drops only the guest
tables so they are recreated with the correct schema by create_all().

Guest tables only:
- guest_sessions
- guest_messages
"""

from typing import Dict, List, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _table_exists(engine: Engine, table_name: str) -> bool:
    """Return True if the table exists in SQLite."""
    query = text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name")
    with engine.connect() as conn:
        row = conn.execute(query, {"name": table_name}).fetchone()
    return row is not None


def _table_info(engine: Engine, table_name: str) -> List[Tuple]:
    """Return PRAGMA table_info rows: (cid, name, type, notnull, dflt_value, pk)."""
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
    return list(rows)


def _columns_set(rows: List[Tuple]) -> Set[str]:
    """Return a set of column names from PRAGMA table_info rows."""
    return {str(r[1]) for r in rows}


def _add_column(engine: Engine, table_name: str, ddl_sql: str) -> None:
    """Add a column via ALTER TABLE."""
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl_sql}"))


def _ensure_unique_index(engine: Engine, index_name: str, table_name: str, column: str) -> None:
    """Create a unique index if it does not already exist."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                f"{index_name} ON {table_name} ({column})"
            )
        )


def _backfill_session_tokens(engine: Engine) -> None:
    """Populate empty session_token values with random bytes."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE guest_sessions
                SET session_token = LOWER(HEX(RANDOMBLOB(24)))
                WHERE session_token IS NULL OR session_token = ''
                """
            )
        )


def _recreate_guest_tables(engine: Engine) -> None:
    """Drop only guest tables so they can be recreated by create_all()."""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS guest_messages"))
        conn.execute(text("DROP TABLE IF EXISTS guest_sessions"))


def _id_pk_is_valid(rows: List[Tuple]) -> bool:
    """Return True if the id column is INTEGER primary key."""
    for cid, name, coltype, notnull, dflt, pk in rows:
        if str(name) == "id":
            t = str(coltype or "").upper()
            return pk == 1 and "INT" in t
    return False


def _ensure_columns(engine: Engine, table: str, required: Dict[str, str]) -> None:
    """Ensure required columns exist by adding any missing columns."""
    rows = _table_info(engine, table)
    existing = _columns_set(rows)
    for col, ddl in required.items():
        if col not in existing:
            _add_column(engine, table, ddl)


def migrate_guest_tables(engine: Engine) -> None:
    """Bring guest tables up to date.

    If guest_sessions exists with an invalid primary key on id, drop and
    recreate guest tables. Otherwise, add any missing columns/indexes.
    """
    if not _table_exists(engine, "guest_sessions"):
        return

    rows = _table_info(engine, "guest_sessions")
    if not _id_pk_is_valid(rows):
        _recreate_guest_tables(engine)
        return

    _ensure_columns(
        engine,
        "guest_sessions",
        {
            "session_token": "session_token TEXT",
            "figure_slug": "figure_slug TEXT",
            "question_count": "question_count INTEGER DEFAULT 0",
            "created_at": "created_at DATETIME",
            "expires_at": "expires_at DATETIME",
        },
    )
    _backfill_session_tokens(engine)
    _ensure_unique_index(engine, "uq_guest_sessions_session_token", "guest_sessions", "session_token")

    if _table_exists(engine, "guest_messages"):
        _ensure_columns(
            engine,
            "guest_messages",
            {
                "session_id": "session_id INTEGER",
                "role": "role TEXT",
                "message": "message TEXT",
                "model_used": "model_used TEXT",
                "timestamp": "timestamp DATETIME",
            },
        )
