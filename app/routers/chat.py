"""Router for handling threaded chat interactions, thread creation, and message completions."""

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db_chat
from app.utils.security import get_current_user

router = APIRouter(tags=["Chat"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ThreadCreatePayload(BaseModel):
    """Request body for creating a new conversation thread."""
    user_id: int = Field(...)
    title: Optional[str] = None


@router.post("/threads", status_code=201)
def create_thread(payload: ThreadCreatePayload, db: Session = Depends(get_db_chat)) -> dict:
    """Create a new thread for the provided user and return its identity."""
    user = crud.get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    title = payload.title or "New thread"
    thread_in = schemas.ThreadCreate(user_id=payload.user_id, title=title, figure_slug=None)
    thread = crud.create_thread(db, thread_in)
    return {"thread_id": thread.id, "user_id": thread.user_id, "title": thread.title}


@router.get("/threads/{thread_id}", response_model=schemas.ThreadRead)
def get_thread(
    thread_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ThreadRead:
    """Return a single thread’s metadata if owned by the current user."""
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")
    return thread


@router.get(
    "/threads/{thread_id}/messages",
    response_model=List[schemas.ChatMessageRead],
)
def get_thread_messages(
    thread_id: int,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.ChatMessageRead]:
    """Return all messages in a thread if the current user owns the thread."""
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")
    return crud.get_messages_by_thread(db, thread_id, limit=1000)


@router.post("/complete", response_class=RedirectResponse)
def chat_complete(
    request: Request,
    db: Session = Depends(get_db_chat),
    user_id: int = Form(...),
    message: str = Form(...),
    thread_id: Optional[int] = Form(None),
) -> RedirectResponse:
    """
    Handle a chat form submission, ensuring a thread exists,
    saving the user message, generating a model reply, saving it,
    and redirecting to the user's threads page.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if thread_id is None:
        thread_in = schemas.ThreadCreate(user_id=user_id, title="New thread", figure_slug=None)
        thread = crud.create_thread(db, thread_in)
        thread_id = thread.id

    user_msg = schemas.ChatMessageCreate(
        user_id=user_id,
        role="user",
        message=message,
        thread_id=thread_id,
    )
    crud.create_chat_message(db, user_msg)

    messages = crud.get_messages_by_thread(db, thread_id)
    formatted_messages = [
        {"role": "system", "content": "You are a helpful and accurate historical guide."}
    ]
    formatted_messages += [{"role": m.role, "content": m.message} for m in messages]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=formatted_messages,
        temperature=0.7,
    )
    answer = response.choices[0].message.content.strip()

    assistant_msg = schemas.ChatMessageCreate(
        user_id=user_id,
        role="assistant",
        message=answer,
        thread_id=thread_id,
    )
    crud.create_chat_message(db, assistant_msg)

    return RedirectResponse(url=f"/user/{user_id}/threads", status_code=303)
