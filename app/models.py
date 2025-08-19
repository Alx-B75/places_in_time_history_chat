"""SQLAlchemy models for users, chats, threads, historical figures, and guest trial sessions.

This module extends your existing schema to support a trial-before-registration flow:

- Adds `GuestSession`, an ephemeral, UUID-keyed session persisted in the DB.
- Updates `Thread` so it can be owned either by a registered `User` (user_id)
  or by a `GuestSession` (guest_session_id).
- Leaves `Chat` and figure models intact, preserving your current data layout.

Migration notes
---------------
1) Create table `guest_sessions` with columns:
   - id (UUID string, PK)
   - created_at, expires_at
   - message_count (int)
   - max_messages (int; default=3)

2) Alter `threads.user_id` to be NULLABLE (previously NOT NULL).

3) Add `threads.guest_session_id` (nullable) with index and FK to `guest_sessions(id)`.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.figures_database import FigureBase


# === Main App Models ===


class Chat(Base):
    """Represents a single message in a chat conversation between a user and the chatbot."""

    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    model_used = Column(String, nullable=True)
    source_page = Column(String, nullable=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)
    summary_of = Column(Integer, ForeignKey("chats.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chats")
    thread = relationship("Thread", back_populates="chats", lazy="joined")
    summary_parent = relationship("Chat", remote_side=[id], lazy="joined")

    def __repr__(self) -> str:
        return f"<Chat id={self.id} role={self.role!r} thread_id={self.thread_id}>"


class User(Base):
    """Represents a user who can submit chats."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    chats = relationship("Chat", back_populates="user", cascade="all, delete")
    threads = relationship("Thread", back_populates="user", cascade="all, delete")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class GuestSession(Base):
    """Ephemeral session used to meter guest trial usage before registration.

    A `GuestSession` is keyed by a UUID string and persisted so the backend
    can enforce a maximum number of guest messages. The UUID is also stored
    in an HttpOnly cookie (e.g., `pit_guest`) on the client.
    """

    __tablename__ = "guest_sessions"

    id = Column(String(36), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    message_count = Column(Integer, nullable=False, default=0)
    max_messages = Column(Integer, nullable=False, default=3)

    # Backref from threads linked to this guest session.
    threads = relationship("Thread", back_populates="guest_session")

    @staticmethod
    def new(max_messages: int = 3, days_valid: int = 7) -> "GuestSession":
        """Create a new guest session with a fresh UUID and expiry."""
        return GuestSession(
            id=str(uuid.uuid4()),
            # using naive UTC would also be fine, but we keep tz-aware like other fields
            expires_at=datetime.utcnow() + timedelta(days=days_valid),
            message_count=0,
            max_messages=max_messages,
        )

    def remaining(self) -> int:
        """Return remaining messages allowed in the guest trial."""
        remaining = self.max_messages - (self.message_count or 0)
        return max(0, remaining)

    def __repr__(self) -> str:
        return (
            f"<GuestSession id={self.id} used={self.message_count}/"
            f"{self.max_messages}>"
        )


class Thread(Base):
    """Represents a conversation thread grouping related messages.

    Ownership rules
    ---------------
    - Registered user: `user_id` is set, `guest_session_id` is NULL.
    - Guest trial: `guest_session_id` is set, `user_id` may be NULL.
    - Exactly one of these should be set in normal operation.
    """

    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)

    # CHANGED: make nullable=True to allow guest-owned threads
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    figure_slug = Column(String, nullable=True)

    # NEW: link guest-owned threads to their session
    guest_session_id = Column(String(36), ForeignKey("guest_sessions.id"), nullable=True)

    # Indices to help common lookups
    __table_args__ = (
        Index("ix_threads_user_id_created_at", "user_id", "created_at"),
        Index("ix_threads_guest_session_id", "guest_session_id"),
    )

    user = relationship("User", back_populates="threads")
    guest_session = relationship("GuestSession", back_populates="threads")

    chats = relationship("Chat", back_populates="thread", cascade="all, delete-orphan")

    def owned_by_user(self) -> bool:
        """Return True if the thread is owned by a registered user."""
        return self.user_id is not None

    def owned_by_guest(self) -> bool:
        """Return True if the thread is linked to a guest session."""
        return self.guest_session_id is not None

    def __repr__(self) -> str:
        return (
            f"<Thread id={self.id} user_id={self.user_id} "
            f"guest_session_id={self.guest_session_id} figure_slug={self.figure_slug!r}>"
        )


# === Figures DB Models ===


class HistoricalFigure(FigureBase):
    """Represents a historical figure relevant to the Places in Time project.

    JSON fields (e.g., roles, wiki_links) are stored as TEXT in SQLite and decoded manually.
    """

    __tablename__ = "historical_figures"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    main_site = Column(String)
    related_sites = Column(Text)
    era = Column(String)
    roles = Column(Text)
    short_summary = Column(Text)
    long_bio = Column(Text)
    echo_story = Column(Text)
    image_url = Column(String)
    sources = Column(Text)
    wiki_links = Column(Text)
    quote = Column(Text)
    persona_prompt = Column(Text, nullable=True)
    birth_year = Column(Integer)
    death_year = Column(Integer)
    verified = Column(Integer, default=0)

    contexts = relationship(
        "FigureContext",
        backref="figure",
        primaryjoin="HistoricalFigure.slug == foreign(FigureContext.figure_slug)",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        """Convert this figure to a Python dict with decoded JSON fields."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "main_site": self.main_site,
            "related_sites": json.loads(self.related_sites) if self.related_sites else [],
            "era": self.era,
            "roles": json.loads(self.roles) if self.roles else [],
            "short_summary": self.short_summary,
            "long_bio": self.long_bio,
            "echo_story": self.echo_story,
            "image_url": self.image_url,
            "sources": json.loads(self.sources) if self.sources else {},
            "wiki_links": json.loads(self.wiki_links) if self.wiki_links else {},
            "quote": self.quote,
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "verified": bool(self.verified),
        }

    def from_dict(self, data: dict) -> None:
        """Populate fields from a dictionary, encoding JSON fields as strings."""
        self.name = data.get("name")
        self.slug = data.get("slug")
        self.main_site = data.get("main_site")
        self.related_sites = json.dumps(data.get("related_sites", []))
        self.era = data.get("era")
        self.roles = json.dumps(data.get("roles", []))
        self.short_summary = data.get("short_summary")
        self.long_bio = data.get("long_bio")
        self.echo_story = data.get("echo_story")
        self.image_url = data.get("image_url")
        self.sources = json.dumps(data.get("sources", {}))
        self.wiki_links = json.dumps(data.get("wiki_links", {}))
        self.quote = data.get("quote")
        self.birth_year = data.get("birth_year")
        self.death_year = data.get("death_year")
        self.verified = 1 if data.get("verified") else 0


class FigureContext(FigureBase):
    """Stores original source context for a historical figure, used for grounding."""

    __tablename__ = "figure_contexts"

    id = Column(Integer, primary_key=True)
    figure_slug = Column(String, index=True)
    source_name = Column(String)
    source_url = Column(String)
    content_type = Column(String)
    content = Column(Text)
    is_manual = Column(Integer, default=0)
