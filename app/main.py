"""
Main FastAPI application entry point for Places in Time History Chat.

This module configures the API, static frontend, CORS, startup tasks, and
provides a health endpoint that verifies configuration and RAG availability.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import Base as ChatBase
from app.database import SQLALCHEMY_DATABASE_URL as CHAT_DB_URL
from app.database import engine as chat_engine
from app.database import get_db_chat
from app.figures_database import FigureBase
from app.figures_database import SQLALCHEMY_DATABASE_URL as FIGURES_DB_URL
from app.figures_database import engine as figures_engine
from app.routers import admin, ask, auth, chat, figures, guest
from app.routers import admin_rag  # new contexts CRUD router
from app.settings import get_settings
from app.utils.security import get_current_user


_settings = get_settings()

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static_frontend"


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
    _ = models  # ensure model metadata is imported
    ChatBase.metadata.create_all(bind=chat_engine)
    FigureBase.metadata.create_all(bind=figures_engine)
    from app.startup_ingest import maybe_ingest_seed_csv

    maybe_ingest_seed_csv(None)
    yield



app = FastAPI(redirect_slashes=True, lifespan=lifespan)

# CORS for Vite dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
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
app.include_router(admin_rag.router)  # per-figure RAG context CRUD

# Mount SPA only if static_frontend exists
static_dir = (Path(__file__).resolve().parent.parent / "static_frontend")

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

    from fastapi import Request
    from fastapi.responses import FileResponse

    # Catch-all for SPA routes
    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{path:path}", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    @app.get("/{path:path}", include_in_schema=False)
    async def spa_catchall(request: Request, path: str = ""):
        """
        Serve index.html for SPA client routing (/, /admin, /admin/*, etc).
        """
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return Response(content="<h1>index.html not found</h1>", media_type="text/html", status_code=404)


@app.get("/health")
def health() -> JSONResponse:
    """
    Return a configuration and dependency health report.
    """
    keys_present = {
        "OPENAI_API_KEY": bool(_settings.openai_api_key),
        "OPENROUTER_API_KEY": bool(_settings.openrouter_api_key),
    }
    rag_status = {"enabled": _settings.rag_enabled, "ok": False, "detail": None}
    try:
        if _settings.rag_enabled:
            from app.vector.chroma_client import get_figure_context_collection

            collection = get_figure_context_collection()
            _ = collection.name
            rag_status["ok"] = True
    except Exception as exc:
        rag_status["ok"] = False
        rag_status["detail"] = str(exc)

    payload = {
        "ok": True,
        "chat_db_url": CHAT_DB_URL,
        "figures_db_url": FIGURES_DB_URL,
        "keys_present": keys_present,
        "rag": rag_status,
        "debug": {"guest_prompt_debug": _settings.guest_prompt_debug},
    }
    return JSONResponse(payload)


@app.get(
    "/threads/user/{user_id}",
    response_model=List[schemas.ThreadRead],
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
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access these threads")
    return crud.get_threads_by_user(db, user_id)


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/user/{user_id}/threads", response_class=FileResponse)
def serve_threads_page(user_id: int) -> FileResponse:
    # consume for linter; file is static
    _ = user_id
    return FileResponse(STATIC_DIR / "threads.html", media_type="text/html")


@app.get("/guest/{slug}", response_class=FileResponse)
def serve_guest_page(slug: str) -> FileResponse:
    # slug is only for client-side routing in this static page
    _ = slug
    return FileResponse(STATIC_DIR / "guest.html", media_type="text/html")


@app.get("/ui/figures", response_class=FileResponse)
def serve_figures_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "figures.html", media_type="text/html")


@app.get("/admin/ui", response_class=FileResponse)
def serve_admin_ui() -> FileResponse:
    """
    Serve the Admin Dashboard UI (landing/overview).
    """
    return FileResponse(STATIC_DIR / "admin.html", media_type="text/html")


@app.get("/admin/figures-ui", response_class=FileResponse, include_in_schema=False)
def serve_admin_figures_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin_figures.html", media_type="text/html")


@app.get("/admin/figure-ui/{slug}", response_class=FileResponse, include_in_schema=False)
def serve_admin_figure_edit_ui(slug: str) -> FileResponse:
    _ = slug  # consumed for path binding; page is static
    return FileResponse(STATIC_DIR / "admin_figure_edit.html", media_type="text/html")


@app.get("/main.js", response_class=FileResponse)
def serve_main_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "main.js", media_type="application/javascript")


@app.get("/style.css", response_class=FileResponse)
def serve_style_css() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@app.get("/logo.png", response_class=FileResponse)
def serve_logo_png() -> FileResponse:
    return FileResponse(STATIC_DIR / "logo.png", media_type="image/png")


@app.get("/threads_visual.png", response_class=FileResponse)
def serve_threads_visual() -> FileResponse:
    return FileResponse(STATIC_DIR / "threads_visual.png", media_type="image/png")


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


@app.get("/debug/routes")
def debug_routes():
    return [route.path for route in app.routes]


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
