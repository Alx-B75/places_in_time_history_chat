"""Seed ingestion for historical figures data.

This module loads a CSV seed file containing historical figures and upserts
records into the figures database. It is idempotent and only re-runs when the
input CSV content changes. The primary goal is to ensure that persona_prompt
is present for each figure, while also updating other basic fields when
available.

Environment
-----------
FIGURES_SEED_CSV : str
    Optional absolute or relative path to the figures CSV file.
    Defaults to "<repo>/data/figures_cleaned.csv".

FIGURES_SEED_STAMP : str
    Optional path to a checksum stamp file. Defaults to
    "<repo>/data/.figures_seed.sha256".
"""

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.orm import Session

from app import models
from app.figures_database import FigureSessionLocal


def _repo_root() -> Path:
    """
    Return the repository root directory based on this file location.

    Returns
    -------
    pathlib.Path
        Absolute path to the repository root.
    """
    return Path(__file__).resolve().parents[1]


def _default_csv_path() -> Path:
    """
    Return the default CSV path under the data directory.

    Returns
    -------
    pathlib.Path
        Default figures CSV file path.
    """
    return _repo_root() / "data" / "figures_cleaned.csv"


def _default_stamp_path() -> Path:
    """
    Return the default checksum stamp file path under the data directory.

    Returns
    -------
    pathlib.Path
        Default stamp file path.
    """
    return _repo_root() / "data" / ".figures_seed.sha256"


def _resolve_paths() -> Tuple[Path, Path]:
    """
    Resolve the CSV and stamp file paths from the environment or defaults.

    Returns
    -------
    tuple[pathlib.Path, pathlib.Path]
        Paths for the CSV input and checksum stamp output.
    """
    csv_env = os.getenv("FIGURES_SEED_CSV")
    stamp_env = os.getenv("FIGURES_SEED_STAMP")
    csv_path = Path(csv_env).expanduser().resolve() if csv_env else _default_csv_path()
    stamp_path = Path(stamp_env).expanduser().resolve() if stamp_env else _default_stamp_path()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    return csv_path, stamp_path


def _file_sha256(path: Path) -> str:
    """
    Compute the SHA256 checksum of a file.

    Parameters
    ----------
    path : pathlib.Path
        File to hash.

    Returns
    -------
    str
        Hex-encoded SHA256 digest.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_stamp(path: Path) -> Optional[str]:
    """
    Read a previously stored checksum from disk.

    Parameters
    ----------
    path : pathlib.Path
        Stamp file path.

    Returns
    -------
    str | None
        Stored checksum value, or None if not present.
    """
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _write_stamp(path: Path, checksum: str) -> None:
    """
    Write a checksum to disk.

    Parameters
    ----------
    path : pathlib.Path
        Stamp file path.
    checksum : str
        Hex-encoded SHA256 digest.
    """
    path.write_text(checksum, encoding="utf-8")


def _load_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    """
    Load rows from a CSV file using the header row for keys.

    Parameters
    ----------
    csv_path : pathlib.Path
        Input CSV path.

    Returns
    -------
    list[dict[str, str]]
        List of row dictionaries keyed by column name.
    """
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _parse_json_field(raw: Optional[str], default) -> str:
    """
    Parse a JSON-like string to canonical JSON, returning a serialized string.

    Parameters
    ----------
    raw : str | None
        Raw field value that may already be JSON or empty.
    default : Any
        Default Python object to use when parsing fails.

    Returns
    -------
    str
        JSON-serialized string value.
    """
    if raw is None or str(raw).strip() == "":
        return json.dumps(default, ensure_ascii=False)
    try:
        val = json.loads(raw)
    except Exception:
        return json.dumps(default, ensure_ascii=False)
    return json.dumps(val, ensure_ascii=False)


def _coerce_int(raw: Optional[str]) -> Optional[int]:
    """
    Convert a string to an integer if possible.

    Parameters
    ----------
    raw : str | None
        Raw value.

    Returns
    -------
    int | None
        Parsed integer or None.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None


def _normalize_row(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Normalize a CSV row to the HistoricalFigure schema keys.

    Parameters
    ----------
    row : dict[str, str]
        Raw CSV row.

    Returns
    -------
    dict[str, str]
        Normalized mapping suitable for upsert.
    """
    return {
        "name": row.get("name", "").strip(),
        "slug": row.get("slug", "").strip(),
        "main_site": row.get("main_site", "").strip(),
        "related_sites": _parse_json_field(row.get("related_sites"), []),
        "era": row.get("era", "").strip(),
        "roles": _parse_json_field(row.get("roles"), []),
        "short_summary": row.get("short_summary", "").strip(),
        "long_bio": row.get("long_bio", "").strip(),
        "echo_story": row.get("echo_story", "").strip(),
        "image_url": row.get("image_url", "").strip(),
        "sources": _parse_json_field(row.get("sources"), {}),
        "wiki_links": _parse_json_field(row.get("wiki_links"), {}),
        "quote": row.get("quote", "").strip(),
        "persona_prompt": row.get("persona_prompt", "").strip(),
        "birth_year": _coerce_int(row.get("birth_year")),
        "death_year": _coerce_int(row.get("death_year")),
        "verified": 1 if str(row.get("verified", "")).strip() in {"1", "true", "True"} else 0,
    }


def _upsert_figure(db: Session, data: Dict[str, Any]) -> Tuple[bool, bool]:
    """
    Upsert a single figure by slug.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Figures database session.
    data : dict[str, str]
        Normalized figure data.

    Returns
    -------
    tuple[bool, bool]
        A tuple (created, updated) flags.
    """
    slug = data.get("slug")
    if not slug:
        return False, False

    existing = (
        db.query(models.HistoricalFigure)
        .filter(models.HistoricalFigure.slug == slug)
        .first()
    )
    if existing:
        changed = False
        fields = [
            "name",
            "main_site",
            "related_sites",
            "era",
            "roles",
            "short_summary",
            "long_bio",
            "echo_story",
            "image_url",
            "sources",
            "wiki_links",
            "quote",
            "persona_prompt",
            "birth_year",
            "death_year",
            "verified",
        ]
        for key in fields:
            new_val = data.get(key)
            if getattr(existing, key) != new_val:
                setattr(existing, key, new_val)
                changed = True
        if changed:
            db.add(existing)
        return False, changed

    rec = models.HistoricalFigure(
        name=data.get("name"),
        slug=slug,
        main_site=data.get("main_site"),
        related_sites=data.get("related_sites"),
        era=data.get("era"),
        roles=data.get("roles"),
        short_summary=data.get("short_summary"),
        long_bio=data.get("long_bio"),
        echo_story=data.get("echo_story"),
        image_url=data.get("image_url"),
        sources=data.get("sources"),
        wiki_links=data.get("wiki_links"),
        quote=data.get("quote"),
        persona_prompt=data.get("persona_prompt"),
        birth_year=data.get("birth_year"),
        death_year=data.get("death_year"),
        verified=data.get("verified"),
    )
    db.add(rec)
    return True, False


def maybe_ingest_seed_csv(logger) -> Tuple[bool, str]:
    """
    Ingest the figures CSV if its content has changed since the last run.

    Parameters
    ----------
    logger : logging.Logger
        Logger to record progress and outcomes.

    Returns
    -------
    tuple[bool, str]
        Tuple indicating whether ingestion ran and a human-readable report.
    """
    csv_path, stamp_path = _resolve_paths()
    if not csv_path.exists():
        return False, f"CSV not found at {csv_path}"

    current_sum = _file_sha256(csv_path)
    previous_sum = _read_stamp(stamp_path)
    if previous_sum == current_sum:
        # Guard against the scenario where the checksum stamp exists but the
        # database is empty (e.g. a reset of figures.db without removing the
        # stamp). In that case we still want to ingest.
        db_empty = False
        _check = FigureSessionLocal()
        try:
            try:
                db_empty = _check.query(models.HistoricalFigure).count() == 0
            except Exception:
                # If the table doesn't exist yet, treat as empty forcing ingest.
                db_empty = True
        finally:
            _check.close()
        if not db_empty:
            return False, "No changes detected in figures CSV (rows already present)"
        # Fall through to ingestion despite matching checksum because DB is empty.

    rows = _load_csv_rows(csv_path)
    created = 0
    updated = 0
    skipped = 0

    db = FigureSessionLocal()
    try:
        for raw in rows:
            data = _normalize_row(raw)
            if not data.get("slug"):
                skipped += 1
                continue
            c, u = _upsert_figure(db, data)
            created += int(c)
            updated += int(u)
        db.commit()
    finally:
        db.close()

    _write_stamp(stamp_path, current_sum)
    report = f"CSV processed: created={created}, updated={updated}, skipped={skipped}"
    return True, report
