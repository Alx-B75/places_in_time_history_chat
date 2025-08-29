"""
CSV ingestion utilities for historical figures.

This module provides idempotent, slug-based upsert of HistoricalFigure rows
from a CSV file using the standard library csv module.

Environment variables
---------------------
FIGURES_CSV_MAPPING : str, optional
    JSON mapping where keys are CSV headers and values are model field names.

Notes
-----
JSON-capable fields:
- roles, related_sites, sources, wiki_links

Integer fields:
- birth_year, death_year, verified
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from sqlalchemy.orm import Session

from app import models

_JSON_FIELDS = {"roles", "related_sites", "sources", "wiki_links"}
_INT_FIELDS = {"birth_year", "death_year", "verified"}
_STR_FIELDS = {
    "name",
    "slug",
    "main_site",
    "era",
    "short_summary",
    "long_bio",
    "echo_story",
    "image_url",
    "quote",
    "persona_prompt",
    "related_sites",
    "roles",
    "sources",
    "wiki_links",
}
_ALL_FIELDS = _STR_FIELDS | _INT_FIELDS


def _coerce_int(value: str) -> Any:
    """
    Convert a string value to int when possible.

    Parameters
    ----------
    value : str

    Returns
    -------
    int | None | str
        Parsed integer, None for empty, or original string on failure.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return value


def _coerce_json_field(value: str, fallback_container: str) -> Any:
    """
    Parse a JSON-capable field; fallback to a basic structure on parse failure.

    Parameters
    ----------
    value : str
    fallback_container : str
        Either "list" or "dict".

    Returns
    -------
    Any
        Parsed JSON, list, dict, string, or None.
    """
    if value is None:
        return [] if fallback_container == "list" else {}
    s = str(value).strip()
    if s == "":
        return [] if fallback_container == "list" else {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        if fallback_container == "list":
            return [s]
        return {"value": s}


def _normalize_row(row: Dict[str, Any], header_map: Dict[str, str]) -> Dict[str, Any]:
    """
    Normalize a CSV row into model field names with basic type coercion.

    Parameters
    ----------
    row : dict
        CSV row keyed by CSV headers.
    header_map : dict
        Mapping of CSV header to model field name.

    Returns
    -------
    dict
        Normalized field dict.
    """
    out: Dict[str, Any] = {}
    for csv_key, raw_val in row.items():
        model_key = header_map.get(csv_key)
        if not model_key:
            continue
        if model_key not in _ALL_FIELDS:
            continue
        if model_key in _INT_FIELDS:
            out[model_key] = _coerce_int(raw_val)
        elif model_key in _JSON_FIELDS:
            container = "list" if model_key in {"roles", "related_sites"} else "dict"
            out[model_key] = _coerce_json_field(raw_val, container)
        else:
            out[model_key] = None if raw_val is None else str(raw_val).strip()
    return out


def _apply_non_empty_updates(
    target: models.HistoricalFigure, data: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Update a figure with only non-empty values from the provided dict.

    Parameters
    ----------
    target : app.models.HistoricalFigure
    data : dict

    Returns
    -------
    tuple[bool, list[str]]
        Whether any change occurred and list of updated fields.
    """
    changed = False
    updated_fields: List[str] = []

    payload: Dict[str, Any] = {}
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        payload[k] = v

    if not payload:
        return False, updated_fields

    before = target.to_dict()
    target.from_dict({**before, **payload})
    after = target.to_dict()

    for k in payload.keys():
        if before.get(k) != after.get(k):
            changed = True
            updated_fields.append(k)

    return changed, updated_fields


def upsert_figures_from_csv(
    db: Session,
    csv_path: Path,
    header_map: Dict[str, str],
    batch_commit: int = 200,
) -> Dict[str, Any]:
    """
    Upsert HistoricalFigure rows from a CSV file.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
    csv_path : pathlib.Path
    header_map : dict
    batch_commit : int

    Returns
    -------
    dict
        Ingestion report with counts and errors.
    """
    added = 0
    updated = 0
    skipped = 0
    errors: List[str] = []

    if not csv_path.exists():
        return {
            "ok": False,
            "reason": "csv_not_found",
            "path": str(csv_path),
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "errors": ["CSV path does not exist"],
        }

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row_count = 0
        for row in reader:
            row_count += 1
            try:
                norm = _normalize_row(row, header_map)
                slug = str(norm.get("slug", "")).strip().lower()
                name = norm.get("name")

                if not slug or not name:
                    skipped += 1
                    continue

                existing = (
                    db.query(models.HistoricalFigure)
                    .filter(models.HistoricalFigure.slug == slug)
                    .first()
                )
                if existing is None:
                    new_obj = models.HistoricalFigure()
                    new_obj.from_dict(norm)
                    db.add(new_obj)
                    added += 1
                else:
                    changed, _ = _apply_non_empty_updates(existing, norm)
                    if changed:
                        updated += 1
                    else:
                        skipped += 1

                if (added + updated + skipped) % batch_commit == 0:
                    db.commit()
            except Exception as exc:
                errors.append(f"row {row_count}: {exc!r}")
                skipped += 1

        db.commit()

    return {
        "ok": True,
        "path": str(csv_path),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
