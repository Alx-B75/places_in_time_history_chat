from __future__ import annotations
"""
Main FastAPI application entry point for Places in Time History Chat.

This module configures the API, static frontend, CORS, startup tasks, and
provides a health endpoint that verifies configuration and RAG availability.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.models_llm_profile import LlmProfile  # ensure LlmProfile is registered on ChatBase  # noqa: F401
from app.database import Base as ChatBase
from app.database import SQLALCHEMY_DATABASE_URL as CHAT_DB_URL
from app.database import engine as chat_engine
from app.database import get_db_chat
from app.figures_database import FigureBase
from app.figures_database import SQLALCHEMY_DATABASE_URL as FIGURES_DB_URL
from app.figures_database import engine as figures_engine
from app.routers import admin, ask, auth, chat, figures, guest, data
from app.routers import admin_rag  # new contexts CRUD router
from app.settings import get_settings
import os
from app.utils.security import (
    get_current_user,
    get_admin_user,
    get_current_user_loose,
    get_admin_user_loose,
)


_settings = get_settings()
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static_frontend"

# Ensure chat DB schema exists early for tests (idempotent)
try:
    ChatBase.metadata.create_all(bind=chat_engine)
    # Lightweight migration: ensure threads.age_profile exists
    from sqlalchemy import text as _sqltext
    with chat_engine.begin() as _conn:
        _cols = _conn.execute(_sqltext("PRAGMA table_info('threads')")).fetchall()
        _names = {str(r[1]) for r in _cols}
        if 'age_profile' not in _names:
            _conn.execute(_sqltext("ALTER TABLE threads ADD COLUMN age_profile TEXT"))
        # Ensure chats.sources_json exists for per-message citations
        _c_cols = _conn.execute(_sqltext("PRAGMA table_info('chats')")).fetchall()
        _c_names = {str(r[1]) for r in _c_cols}
        if 'sources_json' not in _c_names:
            _conn.execute(_sqltext("ALTER TABLE chats ADD COLUMN sources_json TEXT"))
except Exception:
    # Non-fatal during import; lifespan will attempt again
    pass


def _allowed_origins() -> List[str]:
    """
    Resolve allowed CORS origins from centralized settings.
    """
    return _settings.allowed_origins


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    App lifecycle: create DBs and run idempotent figures ingest at startup.
    """
    # models import ensures table registration
    ChatBase.metadata.create_all(bind=chat_engine)
    # Lightweight migration: ensure threads.age_profile exists
    try:
        from sqlalchemy import text as _sqltext
        with chat_engine.begin() as conn:
            cols = conn.execute(_sqltext("PRAGMA table_info('threads')")).fetchall()
            names = {str(r[1]) for r in cols}
            if 'age_profile' not in names:
                conn.execute(_sqltext("ALTER TABLE threads ADD COLUMN age_profile TEXT"))
            # Ensure chats.sources_json exists
            ccols = conn.execute(_sqltext("PRAGMA table_info('chats')")).fetchall()
            cnames = {str(r[1]) for r in ccols}
            if 'sources_json' not in cnames:
                conn.execute(_sqltext("ALTER TABLE chats ADD COLUMN sources_json TEXT"))
    except Exception:
        # Non-fatal: if migration fails, insert queries should still work on fresh DBs
        pass
    FigureBase.metadata.create_all(bind=figures_engine)
    from app.startup_ingest import maybe_ingest_seed_csv
    maybe_ingest_seed_csv(None)
    # Dev-only seed of admin + sample users
    if ENVIRONMENT.lower() == "dev":
        from sqlalchemy.orm import Session as _Session
        seed_db: _Session = next(get_db_chat())
        try:
            # Admin user
            if not crud.get_user_by_username(seed_db, username="admin@example.com"):
                from app.utils.security import hash_password
                admin_user = schemas.UserCreate(username="admin@example.com", hashed_password=hash_password("Admin!123"))
                u = crud.create_user(seed_db, admin_user)
                u.role = "admin"
                seed_db.add(u)
            # Sample user for smoke tests
            if not crud.get_user_by_username(seed_db, username="sample@example.com"):
                from app.utils.security import hash_password
                sample_user = schemas.UserCreate(username="sample@example.com", hashed_password=hash_password("Sample!123"))
                crud.create_user(seed_db, sample_user)
            seed_db.commit()
        finally:
            seed_db.close()
    yield




app = FastAPI(redirect_slashes=True, lifespan=lifespan)

@app.get("/admin/ui", response_class=FileResponse)
def serve_admin_ui() -> FileResponse:
    """Serve the Admin Dashboard UI shell.

    Authorization is enforced by the admin API endpoints this UI calls. Serving
    the HTML itself without auth avoids 401s on initial navigation while still
    keeping admin operations protected.
    """
    path = STATIC_DIR / "admin.html"
    if not path.exists():
        return Response(content="<html><body><h1>Admin UI</h1><p>admin.html not found in static_frontend.</p></body></html>", media_type="text/html")
    return FileResponse(path, media_type="text/html")


@app.get("/admin/figure-rag/{slug}", response_class=FileResponse)
def serve_figure_rag(slug: str) -> FileResponse:
    """Serve the per-figure RAG detail page.

    Authorization enforcement is via the admin API endpoints used by this page.
    """
    path = STATIC_DIR / "figure_rag.html"
    if not path.exists():
        return Response(content="<html><body><h1>Figure RAG</h1><p>figure_rag.html not found.</p></body></html>", media_type="text/html")
    return FileResponse(path, media_type="text/html")


@app.get("/ops/console", response_class=FileResponse)
def serve_ops_console() -> FileResponse:
    """Serve an innocuous admin sign-in page (blank console).

    This page performs an admin-only login via /auth/admin/login and, on success,
    stores tokens in sessionStorage before redirecting to /admin/ui.
    """
    path = STATIC_DIR / "ops_console.html"
    if not path.exists():
        return Response(content="<html><body></body></html>", media_type="text/html")
    return FileResponse(path, media_type="text/html")

# Single CORS middleware combining dev and configured origins to avoid double-wrapping
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        *(_allowed_origins() or []),
    }),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (ensure included once)
app.include_router(admin.router)
app.include_router(ask.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(figures.router)
app.include_router(guest.router)
app.include_router(data.router)
app.include_router(admin_rag.router)  # per-figure RAG context CRUD

# Single static mount (avoid duplicates)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

# ... keep your router includes here (admin, ask, auth, chat, figures, guest) ...
# app.include_router(admin.router)
# app.include_router(ask.router)
# etc.


if ENVIRONMENT.lower() == "dev":
    # Debug route only in development
    from fastapi.routing import APIRoute

    @app.get("/_debug/routes", include_in_schema=False)
    def _debug_routes():
        out = []
        for r in app.routes:
            if isinstance(r, APIRoute):
                out.append({
                    "path": r.path,
                    "methods": sorted(list(r.methods or [])),
                    "endpoint": getattr(r.endpoint, "__name__", str(r.endpoint)),
                })
        out.sort(key=lambda x: (x["path"], ",".join(x["methods"])))
        return out

# Removed broad SPA catch-all which could intercept API routes like /health


@app.get("/health")
def health() -> JSONResponse:
    """Return sanitized configuration and dependency health report (no sensitive paths)."""
    keys_present = {
        "openai_configured": bool(_settings.openai_api_key),
        "openrouter_configured": bool(_settings.openrouter_api_key),
    }
    rag_status = {"enabled": _settings.rag_enabled, "ok": False, "detail": None}
    try:
        if _settings.rag_enabled:
            from app.vector.chroma_client import get_figure_context_collection
            collection = get_figure_context_collection()
            _ = collection.name  # access to confirm client usable
            rag_status["ok"] = True
    except Exception as exc:
        rag_status["ok"] = False
        rag_status["detail"] = str(exc)

    payload = {
        "status": "ok",
        "chat_db_ok": bool(CHAT_DB_URL),
        "figures_db_ok": bool(FIGURES_DB_URL),
        "keys": keys_present,
        "rag": rag_status,
        "guest_prompt_debug": bool(_settings.guest_prompt_debug),
        "environment": ENVIRONMENT,
    }
    return JSONResponse(payload)

# Compatibility endpoints for tests expecting /register and /login at root
@app.post("/register")
def compat_register(payload: dict = Body(...), db: Session = Depends(get_db_chat)):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username and password are required")
    from app.utils.security import hash_password, create_access_token
    user = crud.get_user_by_username(db, username=username)
    if not user:
        user = crud.create_user(db, schemas.UserCreate(username=username, hashed_password=hash_password(password)))
    token = create_access_token(data={"sub": user.username})
    return {"user_id": user.id, "username": user.username, "access_token": token, "token_type": "bearer"}


@app.post("/login")
def compat_login(payload: dict = Body(...), db: Session = Depends(get_db_chat)):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username and password are required")
    from app.utils.security import verify_password, create_access_token
    user = crud.get_user_by_username(db, username=username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(data={"sub": user.username})
    return {"user_id": user.id, "username": user.username, "access_token": token, "token_type": "bearer"}

# Disable legacy HTML login/register pages on GET
@app.get("/login")
def legacy_login_disabled() -> Response:
    return Response(content="Legacy UI disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")

@app.get("/register")
def legacy_register_disabled() -> Response:
    return Response(content="Legacy UI disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")


@app.get(
    "/threads/user/{user_id}",
    response_model=List[schemas.ThreadReadWithPreview],
)
def list_user_threads(
    user_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return all threads for the authenticated user.
    """
    # consume param to satisfy linters (value is used by path binding)
    _ = user_id
    # Defensive: get the actual value, not the SQLAlchemy column
    user_id_val = getattr(current_user, 'id', None)
    if hasattr(user_id_val, 'expression'):  # SQLAlchemy InstrumentedAttribute
        user_id_val = current_user.__dict__.get('id', None)
    if user_id_val is None or int(user_id_val) != int(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access these threads")
    threads = crud.get_threads_by_user(db, user_id)
    if not threads:
        return []
    # Collect first user message per thread in a single query
    thread_ids = [t.id for t in threads]
    # Query all chats for these threads where role='user', ordered by timestamp asc
    chats = (
        db.query(models.Chat)
        .filter(models.Chat.thread_id.in_(thread_ids), models.Chat.role == "user")
        .order_by(models.Chat.thread_id.asc(), models.Chat.timestamp.asc())
        .all()
    )
    first_by_thread: dict[int, models.Chat] = {}
    for c in chats:
        if c.thread_id is None:
            continue
        if c.thread_id not in first_by_thread:
            first_by_thread[c.thread_id] = c

    result: list[dict] = []
    for t in threads:
        first = first_by_thread.get(t.id)
        result.append({
            "id": t.id,
            "user_id": t.user_id,
            "title": t.title,
            "figure_slug": t.figure_slug,
            "created_at": t.created_at,
            "first_user_message": first.message if first else None,
            "first_message_at": first.timestamp if first else None,
        })
    return result


@app.get("/")
def root_index() -> Response:
    return Response(content="API OK", media_type="text/plain")


@app.get("/user/{user_id}/threads")
def legacy_threads_page_disabled(user_id: int, current_user: models.User = Depends(get_current_user_loose)) -> Response:
    _ = user_id
    _ = current_user
    return Response(content="Legacy UI disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")


@app.get("/guest/{slug}")
def legacy_guest_page_disabled(slug: str) -> Response:
    _ = slug
    return Response(content="Legacy UI disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")


@app.get("/ui/figures")
def legacy_figures_ui_disabled() -> Response:
    return Response(content="Legacy UI disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")


## Removed duplicate serve_admin_ui


@app.get("/admin/figures-ui", response_class=FileResponse, include_in_schema=False)
def serve_admin_figures_ui(_: models.User = Depends(get_admin_user_loose)) -> FileResponse:
    return FileResponse(STATIC_DIR / "admin_figures.html", media_type="text/html")


@app.get("/admin/figure-ui/{slug}", response_class=FileResponse, include_in_schema=False)
def serve_admin_figure_edit_ui(slug: str, _: models.User = Depends(get_admin_user_loose)) -> FileResponse:
    _ = slug
    return FileResponse(STATIC_DIR / "admin_figure_edit.html", media_type="text/html")


@app.get("/main.js")
def legacy_main_js_disabled() -> Response:
    return Response(content="Legacy asset disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")


@app.get("/style.css")
def legacy_style_css_disabled() -> Response:
    return Response(content="Legacy asset disabled", status_code=status.HTTP_404_NOT_FOUND, media_type="text/plain")


@app.get("/logo.png")
def legacy_logo_png_disabled() -> Response:
    return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.get("/threads_visual.png")
def legacy_threads_visual_disabled() -> Response:
    return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.get("/favicon.ico")
def serve_favicon_ico() -> Response:
    candidates = [
        STATIC_DIR / "pit-favicon-mark.ico",
        STATIC_DIR / "favicon.ico",
        STATIC_DIR / "icon-192.png",
    ]
    for p in candidates:
        if p.exists():
            media = "image/x-icon" if p.suffix == ".ico" else "image/png"
            return FileResponse(p, media_type=media)
    return Response(status_code=status.HTTP_404_NOT_FOUND)


@app.get("/favicon.svg")
def serve_favicon_svg() -> Response:
    svg_path = STATIC_DIR / "favicon.svg"
    if svg_path.exists():
        return FileResponse(svg_path, media_type="image/svg+xml")
    return Response(status_code=status.HTTP_404_NOT_FOUND)


if ENVIRONMENT.lower() == "dev":
    @app.get("/debug/routes", include_in_schema=False)
    def debug_routes():
        return [getattr(route, 'path', None) for route in app.routes if hasattr(route, 'path')]


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
