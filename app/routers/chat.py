"""Router for handling threaded chat interactions, thread creation, and message completions."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models, schemas, crud
from app.database import get_db_chat

router = APIRouter(tags=["Chat"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ThreadCreatePayload(BaseModel):
    """
    Request body for creating a new conversation thread.
    """
    user_id: int = Field(...)
    title: Optional[str] = None


@router.post("/threads", status_code=201)
def create_thread(payload: ThreadCreatePayload, db: Session = Depends(get_db_chat)) -> dict:
    """
    Creates a new thread for the given user and returns its identity.
    """
    user = crud.get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    title = payload.title or "New thread"
    thread_in = schemas.ThreadCreate(user_id=payload.user_id, title=title, figure_slug=None)
    thread = crud.create_thread(db, thread_in)
    return {"thread_id": thread.id, "user_id": thread.user_id, "title": thread.title}


@router.post("/complete", response_class=RedirectResponse)
def chat_complete(
    request: Request,
    db: Session = Depends(get_db_chat),
    user_id: int = Form(...),
    message: str = Form(...),
    thread_id: Optional[int] = Form(None),
):
    """
    Handles chat form submission for a given thread.
    Saves user message, queries the model, and stores assistant response.
    Redirects back to the thread view.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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

    return RedirectResponse(url=f"/thread/{thread_id}", status_code=303)


@router.post("/thread/{thread_id}/delete", response_class=RedirectResponse)
def delete_thread(thread_id: int, db: Session = Depends(get_db_chat)):
    """
    Deletes a thread and all its associated messages, then redirects to the user thread list.
    """
    thread = crud.get_thread_by_id(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    user_id = thread.user_id

    db.query(models.Chat).filter(models.Chat.thread_id == thread_id).delete()
    db.delete(thread)
    db.commit()

    return RedirectResponse(url=f"/user/{user_id}/threads", status_code=303)
