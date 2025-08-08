"""Router for asking historical figures and viewing figure profiles."""

import os
from typing import Optional, List

from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app import models, schemas, crud
from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.vector.context_retriever import search_figure_context
from app.templating import templates
from app.utils.security import get_current_user

router = APIRouter(
    prefix="/figures",
    tags=["Figures"]
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_figure_db():
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/ask", response_class=HTMLResponse)
def get_ask_figure_page(
    request: Request,
    figure_slug: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    thread_id: Optional[int] = None,
    db: Session = Depends(get_db_chat),
):
    """
    Renders the figure selection page or chat view for a specific figure and thread.
    """
    fig_db = FigureSessionLocal()
    try:
        if not figure_slug:
            figures = crud.get_all_figures(db=fig_db)
            return templates.TemplateResponse("figure_select.html", {
                "request": request,
                "figures": figures,
                "user_id_value": user_id
            })

        figure = crud.get_figure_by_slug(fig_db, slug=figure_slug)
        if not figure:
            raise HTTPException(status_code=404, detail="Figure not found")
    finally:
        fig_db.close()

    thread = crud.get_thread_by_id(db, thread_id) if thread_id else None
    messages = crud.get_messages_by_thread(db, thread_id) if thread else []

    return templates.TemplateResponse("ask_figure.html", {
        "request": request,
        "figure": figure,
        "thread": thread,
        "messages": messages,
        "user_id_value": user_id
    })


@router.post("/ask", response_model=schemas.ChatMessageRead)
async def ask_figure_submit(
    request_data: schemas.AskRequest,
    db: Session = Depends(get_db_chat),
    current_user: models.User = Depends(get_current_user),
):
    """
    Submits a user question to a historical figure and returns the assistant's reply.
    Creates a thread if one does not exist.
    """
    if current_user.id != request_data.user_id:
        raise HTTPException(status_code=403, detail="User ID mismatch")

    fig_db = FigureSessionLocal()
    try:
        figure = crud.get_figure_by_slug(fig_db, slug=request_data.figure_slug)
        if not figure:
            raise HTTPException(status_code=404, detail="Figure not found")
    finally:
        fig_db.close()

    # Thread creation if not provided
    thread_id = request_data.thread_id
    if not thread_id:
        thread = schemas.ThreadCreate(
            user_id=request_data.user_id,
            title=f"Chat with {figure.name}",
            figure_slug=request_data.figure_slug
        )
        new_thread = crud.create_thread(db, thread)
        thread_id = new_thread.id

    # Save user message
    user_msg = schemas.ChatMessageCreate(
        user_id=request_data.user_id,
        role="user",
        message=request_data.message,
        thread_id=thread_id
    )
    crud.create_chat_message(db, user_msg)

    # System prompt + context
    system_prompt = figure.persona_prompt or "You are a helpful historical guide."
    context_chunks = search_figure_context(query=request_data.message, figure_slug=request_data.figure_slug)
    context_text = "\n\n".join([chunk["content"] for chunk in context_chunks])

    # Assemble prompt
    messages = [{"role": "system", "content": system_prompt}]
    if context_text:
        messages.append({"role": "system", "content": f"Relevant historical context:\n{context_text}"})
    messages += [{"role": m.role, "content": m.message} for m in crud.get_messages_by_thread(db, thread_id)]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7
    )
    reply = response.choices[0].message.content.strip()

    # Save assistant reply
    assistant_msg = schemas.ChatMessageCreate(
        user_id=request_data.user_id,
        role="assistant",
        message=reply,
        thread_id=thread_id
    )
    return crud.create_chat_message(db, assistant_msg)


@router.get("/", response_model=List[schemas.HistoricalFigureRead])
def read_all_figures(skip: int = 0, limit: int = 100, db: Session = Depends(get_figure_db)):
    """
    Returns all historical figures for listing or UI display.
    """
    return crud.get_all_figures(db, skip=skip, limit=limit)


@router.get("/{slug}", response_model=schemas.HistoricalFigureDetail)
def read_figure_by_slug(slug: str, db: Session = Depends(get_figure_db)):
    """
    Returns full detail of a historical figure including context.
    """
    figure = crud.get_figure_by_slug(db, slug=slug)
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")
    return figure
