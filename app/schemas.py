"""Pydantic schemas for request and response validation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# === User Schemas ===

class UserCreate(BaseModel):
    """Accepts user input for registration."""
    username: str
    hashed_password: str


class UserRead(BaseModel):
    """Returns user data after registration – excludes password."""
    id: int
    username: str

    model_config = {"from_attributes": True}


# === Thread Schemas ===

class ThreadCreate(BaseModel):
    """Schema for creating a new conversation thread."""
    user_id: int
    title: Optional[str] = None
    figure_slug: Optional[str] = None


class ThreadRead(ThreadCreate):
    """Schema for reading an existing thread with metadata."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# === Chat Message Schemas ===

class ChatMessageCreate(BaseModel):
    """Schema for creating a single message in a conversation."""
    user_id: Optional[int]
    role: str  # 'user', 'assistant', 'system', or 'summary'
    message: str
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    thread_id: Optional[int] = None
    summary_of: Optional[int] = None


class ChatMessageRead(ChatMessageCreate):
    """Schema for reading a stored chat message."""
    id: int
    timestamp: datetime

    model_config = {"from_attributes": True}


class ChatCreateRequest(BaseModel):
    """Input schema for /ask endpoint – client sends only these fields."""
    message: str
    user_id: int
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    figure_slug: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """Schema for submitting a new user message for LLM completion."""
    user_id: int
    message: str
    model_used: Optional[str] = "gpt-4o-mini"
    source_page: Optional[str] = None
    thread_id: Optional[int] = None


# === Ask Flow ===

class AskRequest(BaseModel):
    """Schema for incoming questions to the chatbot."""
    user_id: int
    message: str
    figure_slug: Optional[str] = None
    source_page: Optional[str] = None
    model_used: Optional[str] = "gpt-4o-mini"
    thread_id: Optional[int] = None


class AskResponse(BaseModel):
    """Schema for chatbot responses returned by the /ask endpoint."""
    id: int
    user_id: int
    role: str
    message: str
    model_used: Optional[str] = None
    source_page: Optional[str] = None
    thread_id: Optional[int] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


# === Historical Figure Schemas ===

class FigureContextRead(BaseModel):
    """Schema to return context entries tied to a historical figure."""
    id: int
    figure_slug: str
    source_name: Optional[str]
    source_url: Optional[str]
    content_type: Optional[str]
    content: str
    is_manual: int

    model_config = {"from_attributes": True}


class HistoricalFigureRead(BaseModel):
    """Summary schema for listing historical figures."""
    id: int
    name: str
    slug: str
    era: Optional[str]
    roles: Optional[str]
    image_url: Optional[str]
    short_summary: Optional[str]

    model_config = {"from_attributes": True}


class HistoricalFigureDetail(HistoricalFigureRead):
    """Detailed schema for a single historical figure with full data and context entries."""
    long_bio: Optional[str]
    echo_story: Optional[str]
    quote: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    main_site: Optional[str]
    related_sites: Optional[str]
    sources: Optional[str]
    wiki_links: Optional[str]
    verified: Optional[int]
    contexts: List[FigureContextRead] = []
