"""
Question-answering routes for historical figure chats.

This router composes prompts via the unified builder and persists messages
to the chat database.
"""

from __future__ import annotations

from typing import Any, Dict, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from app.services.llm_client import LlmClient
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.settings import get_settings
from app.utils.prompt import build_prompt
from app.utils.security import get_current_user


router = APIRouter(tags=["Ask"])

_settings = get_settings()
llm_client = LlmClient()


from app.config.llm_config import llm_config
import json as _json

def generate_answer(context: list[dict], prompt: str, *, model: str | None = None, temperature: float | None = None):
    """
    Thin wrapper to generate an answer from the LLM and return (answer, usage).

    Exposed at module scope so tests can monkeypatch this function for
    deterministic results without touching the LlmClient internals.
    """
    chosen_model = model or llm_config.model
    chosen_temp = temperature if temperature is not None else llm_config.temperature
    response = llm_client.generate(messages=context, model=chosen_model, temperature=chosen_temp)
    answer = response["choices"][0]["message"]["content"].strip() if response.get("choices") else ""
    usage = response.get(
        "usage",
        {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    return answer, usage


def get_figure_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session bound to the figures database.

    Yields
    ------
    sqlalchemy.orm.Session
        Database session for the figures database.
    """
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/ask")
def ask(
    payload: schemas.AskRequest,
    db: Session = Depends(get_db_chat),
    db_fig: Session = Depends(get_figure_db),
    current_user: models.User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Answer a user question with persona and optional RAG context.

    Parameters
    ----------
    payload : app.schemas.AskRequest
        Request payload including message and optional figure/thread data.
    db : sqlalchemy.orm.Session
        Chat database session.
    db_fig : sqlalchemy.orm.Session
        Figures database session.
    current_user : app.models.User
        Authenticated user.

    Returns
    -------
    dict
        The answer, sources, thread_id, and usage metadata.
    """
    if current_user.id != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    thread = None
    if payload.thread_id is not None:
        thread = crud.get_thread_by_id(db, payload.thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        if thread.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    else:
        thread_in = schemas.ThreadCreate(
            user_id=current_user.id,
            title="Ask session",
            figure_slug=payload.figure_slug,
        )
        thread = crud.create_thread(db, thread_in)

    resolved_slug: Optional[str] = None
    if thread and getattr(thread, "figure_slug", None):
        resolved_slug = thread.figure_slug
    elif payload.figure_slug:
        resolved_slug = payload.figure_slug

    user_msg = schemas.ChatMessageCreate(
        user_id=current_user.id,
        role="user",
        message=payload.message,
        thread_id=thread.id,
        model_used=payload.model_used,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, user_msg)

    # Optionally skip LLM generation (useful for tests)
    if payload.skip_llm:
        return {"answer": "", "sources": [], "thread_id": thread.id, "usage": {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}}

    figure = crud.get_figure_by_slug(db_fig, resolved_slug) if resolved_slug else None
    history = crud.get_messages_by_thread(db, thread.id, limit=1000)
    history_dicts = [{"role": m.role, "message": m.message} for m in history]

    messages, sources = build_prompt(
        figure=figure,
        user_message=payload.message,
        thread_history=history_dicts,
        max_context_chars=4000,
        use_rag=_settings.rag_enabled,
        debug=_settings.guest_prompt_debug,
    )

    model_name = payload.model_used or llm_config.model
    answer, usage = generate_answer(messages, payload.message, model=model_name, temperature=None)

    # Persist actual sources used for this answer so UI can render them.
    sources_json = None
    try:
        if sources:
            sources_json = _json.dumps(sources, ensure_ascii=False)
    except Exception:
        sources_json = None
    assistant_msg = schemas.ChatMessageCreate(
        user_id=current_user.id,
        role="assistant",
        message=answer,
        thread_id=thread.id,
        model_used=model_name,
        source_page=sources_json,
    )
    crud.create_chat_message(db, assistant_msg)

    return {"answer": answer, "sources": sources, "thread_id": thread.id, "usage": usage}
