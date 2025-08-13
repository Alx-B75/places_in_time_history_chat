"""
Question-answering routes for historical figure chats.
"""

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db_chat

router = APIRouter(tags=["Ask"])


def generate_answer(context: List[Dict[str, Any]], prompt: str) -> Tuple[str, Dict[str, int]]:
    """
    Generates an answer and usage metadata from the provided context and prompt.

    This is a placeholder implementation intended to be monkeypatched in tests or
    replaced by a real model integration during runtime.
    """
    return "Not implemented", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@router.post("/ask")
def ask(payload: schemas.AskRequest, db: Session = Depends(get_db_chat)) -> Dict[str, Any]:
    """
    Answers a user question, persists messages, and returns answer, sources, thread id, and usage.

    The request must include user and thread identifiers. The function validates ownership,
    stores the user message, generates an assistant reply, stores it, and returns a response
    payload that includes token usage statistics and any context sources used.
    """
    user = crud.get_user_by_id(db, payload.user_id)
    thread = crud.get_thread_by_id(db, payload.thread_id) if payload.thread_id else None
    if not user or not thread or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="User or thread not found")

    user_msg = schemas.ChatMessageCreate(
        user_id=payload.user_id,
        role="user",
        message=payload.message,
        thread_id=payload.thread_id,
        model_used=payload.model_used,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, user_msg)

    context: List[Dict[str, Any]] = []
    answer, usage = generate_answer(context, payload.message)

    assistant_msg = schemas.ChatMessageCreate(
        user_id=payload.user_id,
        role="assistant",
        message=answer,
        thread_id=payload.thread_id,
        model_used=payload.model_used,
        source_page=payload.source_page,
    )
    crud.create_chat_message(db, assistant_msg)

    sources: List[Dict[str, Any]] = []
    return {
        "answer": answer,
        "sources": sources,
        "thread_id": payload.thread_id,
        "usage": usage,
    }
