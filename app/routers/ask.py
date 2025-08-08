"""Router for handling 'ask a historical figure' AI interactions."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from openai import OpenAI

from app.database import get_db_chat
from app.figures_database import FigureSessionLocal
from app.models import Chat, HistoricalFigure
from app.schemas import AskRequest, AskResponse
from app.vector.context_retriever import search_figure_context

router = APIRouter()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_db_figure():
    db = FigureSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    db_chat: Session = Depends(get_db_chat),
    db_figure: Session = Depends(get_db_figure),
):
    """
    Handles a user question for a specific historical figure.
    Returns an AI-generated response using vector context filtered by figure.
    """
    figure = db_figure.query(HistoricalFigure).filter_by(slug=request.figure_slug).first()
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")

    persona_prompt = (
        figure.persona_prompt
        if figure.persona_prompt
        else f"You are {figure.name}. Answer as this historical figure."
    )

    # Retrieve vector-based context chunks
    results = search_figure_context(
        query=request.message,
        figure_slug=request.figure_slug
    )

    sources_used = []
    context_chunks = []
    for doc in results:
        context_chunks.append(doc["content"])
        if doc["metadata"].get("source"):
            sources_used.append(doc["metadata"]["source"])

    # Construct GPT prompt
    messages = [{"role": "system", "content": persona_prompt}]
    messages += [{"role": "system", "content": chunk} for chunk in context_chunks]
    messages.append({"role": "user", "content": request.message})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    answer = completion.choices[0].message.content.strip()

    # Store conversation entries in chat DB
    db_chat.add_all([
        Chat(
            user_id=request.user_id,
            thread_id=request.thread_id,
            figure_slug=request.figure_slug,
            role="user",
            message=request.message,
            timestamp=datetime.utcnow(),
        ),
        Chat(
            user_id=request.user_id,
            thread_id=request.thread_id,
            figure_slug=request.figure_slug,
            role="assistant",
            message=answer,
            timestamp=datetime.utcnow(),
        ),
    ])
    db_chat.commit()

    return AskResponse(
        id=0,  # You can return real chat ID if needed
        user_id=request.user_id,
        role="assistant",
        message=answer,
        model_used="gpt-4o",
        source_page=request.source_page,
        thread_id=request.thread_id,
        timestamp=datetime.utcnow(),
        sources=sources_used,
    )
