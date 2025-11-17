"""
Ask endpoint and helper to generate answers using the configured LLM.

Exposes:
- POST /ask
- Function generate_answer(...) for tests to monkeypatch
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app import crud, models, schemas
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.utils.prompt import build_prompt
from app.utils.security import get_current_user
from app.services.llm_client import llm_client


router = APIRouter()


def get_figure_db():
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_answer(context: Dict[str, Any], prompt: List[Dict[str, str]], *, model: Optional[str] = None, temperature: Optional[float] = None) -> Tuple[str, Dict[str, Any]]:
    """Call the LLM client and return (answer, usage). Separated for test monkeypatching."""
    resp = llm_client.generate(messages=prompt, model=model, temperature=temperature)
    text = ""
    choices = resp.get("choices") or []
    if choices and isinstance(choices, list):
        msg = choices[0].get("message") or {}
        text = (msg.get("content") or "").strip()
    usage = resp.get("usage", {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None})
    return text, usage


@router.post("/ask")
def ask(payload: schemas.AskRequest, db: Session = Depends(get_db_chat), fig_db: Session = Depends(get_figure_db), current_user: models.User = Depends(get_current_user)):
    # Validate user
    if not crud.get_user_by_id(db, payload.user_id or 0):
        raise HTTPException(status_code=404, detail="User not found")

    # Validate/ensure thread
    thread_id = payload.thread_id
    if thread_id is not None:
        thread = crud.get_thread_by_id(db, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if thread.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        # Create a new thread if none provided
        t = crud.create_thread(db, schemas.ThreadCreate(user_id=payload.user_id, title=payload.figure_slug or "Chat", figure_slug=payload.figure_slug))
        thread_id = t.id

    # Persist the user message
    crud.create_chat_message(db, schemas.ChatMessageCreate(user_id=payload.user_id, role="user", message=payload.message, model_used=payload.model_used, source_page=payload.source_page, thread_id=thread_id))

    # For preview-only posts (no LLM call)
    if payload.skip_llm:
        return {"ok": True, "thread_id": thread_id}

    # Load figure + contexts (if provided)
    figure = None
    if payload.figure_slug:
        figure = crud.get_figure_by_slug(fig_db, slug=payload.figure_slug)

    # Build prompt including minimal history for the thread
    history = [
        {"role": c.role, "message": c.message}
        for c in crud.get_messages_by_thread(db, thread_id, limit=50)
    ]
    messages, sources = build_prompt(
        figure=figure,
        user_message=payload.message,
        thread_history=history,
        max_context_chars=4000,
        use_rag=True,
        debug=False,
    )

    answer, usage = generate_answer({"figure": payload.figure_slug}, messages, model=payload.model_used)

    # Persist assistant message
    msg = crud.create_chat_message(db, schemas.ChatMessageCreate(user_id=payload.user_id, role="assistant", message=answer, model_used=payload.model_used, source_page=payload.source_page, thread_id=thread_id))

    return {
        "answer": answer,
        "sources": sources,
        "usage": usage,
        "thread_id": thread_id,
        "id": msg.id,
    }
