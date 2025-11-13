"""
SQLAlchemy models for users, chats, threads, historical figures, guest chat, and admin audit.

This module defines the core ORM models used by the application. It preserves the
authenticated-user tables and the isolated guest tables, and introduces role-based
access via a new User.role field alongside an AuditLog table for administrative
actions.
"""

import json
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.figures_database import FigureBase


class Chat(Base):
    """
    Represents a single message in a chat conversation between a user and the chatbot.
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
    sources_json = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chats")
    thread = relationship("Thread", back_populates="chats", lazy="joined")
    summary_parent = relationship("Chat", remote_side=[id], lazy="joined")


class User(Base):
    """
    Represents an application user with role-based access.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user", index=True)

    chats = relationship("Chat", back_populates="user", cascade="all, delete")
    threads = relationship("Thread", back_populates="user", cascade="all, delete")
    audit_logs = relationship("AuditLog", back_populates="actor", cascade="all, delete")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")


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
    age_profile = Column(String, nullable=True, index=True, default="general")

    user = relationship("User", back_populates="threads")
    chats = relationship("Chat", back_populates="thread", cascade="all, delete-orphan")


class Favorite(Base):
    """
    Stores a user's favorited historical figures by slug.
    Unique per (user_id, figure_slug).
    """

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "figure_slug", name="uq_favorite_user_figure"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    figure_slug = Column(String, nullable=False, index=True)

    user = relationship("User", back_populates="favorites")


class HistoricalFigure(FigureBase):
    """
    Represents a historical figure relevant to the Places in Time project.
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
            "persona_prompt": self.persona_prompt,
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
        self.persona_prompt = data.get("persona_prompt")
        self.birth_year = data.get("birth_year")
        self.death_year = data.get("death_year")
        self.verified = 1 if data.get("verified") else 0


class FigureContext(FigureBase):
    """
    Stores original source context for a historical figure, used in the chatbot for grounding.
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
    """

    __tablename__ = "guest_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("guest_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    model_used = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("GuestSession", back_populates="messages")


class AuditLog(Base):
    """
    Records administrative actions for auditing and accountability.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False, index=True)
    object_type = Column(String, nullable=False, index=True)
    object_id = Column(String, nullable=True)
    diff_json = Column(Text, nullable=True)
    ip = Column(String, nullable=True)

    actor = relationship("User", back_populates="audit_logs")
