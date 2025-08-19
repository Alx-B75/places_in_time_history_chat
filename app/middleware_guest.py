"""Middleware to provision a GuestSession and cookie for anonymous visitors.

This middleware:
- Skips guest provisioning on auth/docs/static endpoints.
- For other unauthenticated requests, attempts to create a GuestSession row
  and set an HttpOnly cookie. If the `guest_sessions` table is not present
  yet (e.g., before migrations), it fails open (no cookie) to avoid 500s.

Assumptions
-----------
- `app.database` exposes `SessionLocal`.
- `app.models` defines `GuestSession`.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import SessionLocal
from app.models import GuestSession

GUEST_COOKIE_NAME = "pit_guest"

# Endpoints where we do NOT attempt to create a guest session.
_EXCLUDED_PREFIXES = (
    "/auth",           # login/registration
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/favicon.ico",
    "/health",
)


class EnsureGuestSessionMiddleware(BaseHTTPMiddleware):
    """Create a guest session for anonymous visitors and set an HttpOnly cookie."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path or "/"
        # Skip endpoints that shouldn't create guest state
        if path.startswith(_EXCLUDED_PREFIXES):
            return await call_next(request)

        has_auth = "authorization" in request.headers
        has_cookie = GUEST_COOKIE_NAME in request.cookies

        if not has_auth and not has_cookie:
            db: Session = SessionLocal()
            try:
                try:
                    guest = GuestSession.new()
                    db.add(guest)
                    db.commit()
                    db.refresh(guest)

                    response = await call_next(request)
                    response.set_cookie(
                        key=GUEST_COOKIE_NAME,
                        value=guest.id,
                        httponly=True,
                        samesite="Lax",
                        secure=True,  # set False only in local HTTP development if needed
                        max_age=7 * 24 * 3600,
                        path="/",
                    )
                    return response
                except OperationalError:
                    # Table likely not created yet; continue without setting a guest cookie.
                    return await call_next(request)
            finally:
                db.close()

        # Default path: nothing to do, just continue.
        return await call_next(request)
