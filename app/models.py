"""SQLAlchemy models for users, chats, threads, historical figures, and guest chat.

This module defines the core ORM models used by the application. The existing
authenticated-user models are preserved as-is. Two additional models are
introduced to enable a limited guest chat flow without touching the current
authenticated-chat tables or behavior:

1) GuestSession
   Represents an ephemeral, anonymous trial session scoped to a single
   historical figure. Contains a random opaque session token, a server-side
   counter for the number of guest questions asked, and timestamps.

2) GuestMessage
   Stores individual messages exchanged in a guest session. This mirrors the
   structure of Chat but remains isolated so that guest data handling cannot
   impact the authenticated flow.

These guest models allow enforcing a strict question limit server-side while
keeping the existing user/thread/chat logic unchanged.
"""

import json
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.figures_database import FigureBase


class Chat(Base):
    """
    Represents a single message in a chat conversation between a user and the
    chatbot.
    """
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


class User(Base):
    """
    Represents a user who can submit chats.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    chats = relationship("Chat", back_populates="user", cascade="all, delete")
    threads = relationship("Thread", back_populates="user", cascade="all, delete")


class Thread(Base):
    """
    Represents a conversation thread grouping related messages.
    """
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    figure_slug = Column(String, nullable=True)

    user = relationship("User", back_populates="threads")
    chats = relationship(
        "Chat",
        back_populates="thread",
        cascade="all, delete-orphan",
    )


class HistoricalFigure(FigureBase):
    """
    Represents a historical figure relevant to the Places in Time project.

    JSON fields (e.g., roles, wiki_links) are stored as TEXT in SQLite and
    decoded manually.
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
        """
        Convert this figure to a plain dictionary with decoded JSON fields.
        """
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "main_site": self.main_site,
            "related_sites": json.loads(self.related_sites)
            if self.related_sites
            else [],
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
        """
        Populate fields from a dictionary, encoding JSON fields as strings.
        """
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
    """
    Stores original source context for a historical figure, used in the chatbot
    for grounding.
    """
    __tablename__ = "figure_contexts"

    id = Column(Integer, primary_key=True)
    figure_slug = Column(String, index=True)
    source_name = Column(String)
    source_url = Column(String)
    content_type = Column(String)
    content = Column(Text)
    is_manual = Column(Integer, default=0)


class GuestSession(Base):
    """
    Represents a short-lived anonymous session for a specific historical figure.

    A GuestSession is identified by an opaque, random token that is stored in an
    HttpOnly cookie on the client. The server enforces a maximum number of
    questions for the session and can set an optional expiry. This model is
    intentionally separate from the authenticated thread models to prevent any
    coupling or regression risk in existing flows.
    """
    __tablename__ = "guest_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String, unique=True, index=True, nullable=False)
    figure_slug = Column(String, nullable=True)
    question_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    messages = relationship(
        "GuestMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class GuestMessage(Base):
    """
    Represents a single message within a guest session.

    This mirrors the structure of Chat for the authenticated flow but remains
    isolated so that guest data is fully sandboxed.
    """
    __tablename__ = "guest_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("guest_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    model_used = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("GuestSession", back_populates="messages")
