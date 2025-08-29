"""
Startup-triggered ingestion for figures CSV.

This module computes a hash of the CSV file and compares it with a stored hash
on the persistent disk to decide if ingestion is needed. On change, it runs an
idempotent upsert and records the new hash.

Environment variables
---------------------
FIGURES_SEED_CSV_PATH : str
    Path to the seed CSV. Default: ./data/figures_cleaned.csv
FIGURES_INGEST_HASH_PATH : str
    Path to the stored hash file. Default: /data/figures_seed.sha256
FIGURES_CSV_MAPPING : str, optional
    JSON mapping of CSV headers to model fields.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from app.figures_database import FigureSessionLocal
from app.ingest.figures_csv import upsert_figures_from_csv


def _env_csv_path() -> Path:
    """
    Resolve the CSV path from environment or default.

    Returns
    -------
    pathlib.Path
        CSV file path.
    """
    raw = os.getenv("FIGURES_SEED_CSV_PATH", "./data/figures_cleaned.csv")
    return Path(raw).expanduser().resolve()


def _env_hash_path() -> Path:
    """
    Resolve the stored hash path from environment or default.

    Returns
    -------
    pathlib.Path
        Hash file path stored on persistent disk.
    """
    raw = os.getenv("FIGURES_INGEST_HASH_PATH", "/data/figures_seed.sha256")
    p = Path(raw).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _env_header_map() -> Dict[str, str]:
    """
    Parse optional JSON mapping for CSV headers to model fields.

    Returns
    -------
    dict
        Mapping where keys are CSV headers and values are model field names.
    """
    raw = os.getenv("FIGURES_CSV_MAPPING")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _file_sha256(path: Path) -> str:
    """
    Compute the SHA-256 hash of a file.

    Parameters
    ----------
    path : pathlib.Path

    Returns
    -------
    str
        Hex digest of the file contents.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_hash(path: Path) -> str:
    """
    Read a stored hash string from disk.

    Parameters
    ----------
    path : pathlib.Path

    Returns
    -------
    str
        Stored hex digest, or empty string if missing.
    """
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _write_hash(path: Path, digest: str) -> None:
    """
    Write a hash string to disk.

    Parameters
    ----------
    path : pathlib.Path
    digest : str
    """
    path.write_text(digest, encoding="utf-8")


def maybe_ingest_seed_csv(logger) -> Tuple[bool, dict]:
    """
    Ingest the seed CSV if its content has changed.

    Parameters
    ----------
    logger : logging.Logger

    Returns
    -------
    tuple[bool, dict]
        A tuple where the first element indicates whether ingestion ran,
        and the second element is an ingestion report or error info.
    """
    csv_path = _env_csv_path()
    hash_path = _env_hash_path()
    header_map = _env_header_map()

    if not csv_path.exists():
        return False, {
            "ok": False,
            "reason": "csv_not_found",
            "path": str(csv_path),
        }

    new_digest = _file_sha256(csv_path)
    old_digest = _read_hash(hash_path)

    if new_digest == old_digest:
        return False, {
            "ok": True,
            "reason": "hash_unchanged",
            "path": str(csv_path),
        }

    with FigureSessionLocal() as s:  # type: Session
        report = upsert_figures_from_csv(s, csv_path, header_map)

    if report.get("ok"):
        _write_hash(hash_path, new_digest)

    return True, report
