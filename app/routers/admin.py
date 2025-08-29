"""Admin endpoints for operational tasks such as seeding figures.

This module exposes a protected endpoint to trigger the figures CSV ingestion
idempotently in production. It reuses the existing startup ingestion logic and
returns a structured report describing what happened.
"""

from typing import Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, status

from app import models
from app.startup_ingest import maybe_ingest_seed_csv
from app.utils.security import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/figures/ingest", status_code=status.HTTP_200_OK)
def admin_ingest_figures(
    current_user: models.User = Depends(get_current_user),
) -> Dict[str, object]:
    """
    Trigger the figures CSV ingestion and return a report.

    Parameters
    ----------
    current_user : app.models.User
        The authenticated user invoking the operation.

    Returns
    -------
    dict
        A dictionary with keys:
        - "ran": bool indicating whether ingestion executed
        - "report": dict containing details from the ingestion step

    Notes
    -----
    This endpoint requires authentication but does not enforce a special role,
    as the operation is idempotent and safe. To harden further, restrict access
    by user or add a shared secret check as needed.
    """
    ran, report = maybe_ingest_seed_csv(logger=None)  # logger optional here
    if not report.get("ok", True) and report.get("reason") == "csv_not_found":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSV not found at {report.get('path')}",
        )
    return {"ran": ran, "report": report}
