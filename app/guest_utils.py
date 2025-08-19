"""Utilities for resolving the current GuestSession from the request cookie.

Expose a single helper function you can import in routes:
    `get_active_guest_session(request, db) -> Optional[GuestSession]`

This keeps route code clean and centralizes any future changes to
guest-session resolution logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import GuestSession

GUEST_COOKIE_NAME = "pit_guest"


def get_active_guest_session(
    request: Request, db: Session
) -> Optional[GuestSession]:
    """Return the non-expired GuestSession referenced by the `pit_guest` cookie.

    Parameters
    ----------
    request:
        FastAPI/Starlette request, used to read cookies.
    db:
        SQLAlchemy session.

    Returns
    -------
    Optional[GuestSession]
        The active guest session or None if missing or expired.
    """
    guest_id = request.cookies.get(GUEST_COOKIE_NAME)
    if not guest_id:
        return None

    guest = db.query(GuestSession).filter(GuestSession.id == guest_id).first()
    if not guest:
        return None

    # Expiry check (UTC-based).
    if guest.expires_at and guest.expires_at <= datetime.utcnow():
        return None

    return guest
