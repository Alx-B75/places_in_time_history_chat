"""
Centralized runtime settings for the Places in Time service.

This module provides a single validated settings object used across the
application. All configuration is sourced from environment variables and
optional .env files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


def _to_bool(value: Optional[str]) -> bool:
    """
    Convert a string environment value to a boolean.

    Parameters
    ----------
    value : Optional[str]
        The environment variable value.

    Returns
    -------
    bool
        True if the value represents a truthy string, otherwise False.
    """
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """
    Parsed and validated runtime settings.

    Attributes
    ----------
    access_token_expire_minutes : int
        JWT access token lifetime in minutes.
    secret_key : str
        Application secret key for signing and crypto.
    openai_api_key : Optional[str]
        API key for OpenAI.
    openrouter_api_key : Optional[str]
        API key for OpenRouter.
    render : bool
        True when running on Render.
    guest_prompt_debug : bool
        Enables prompt debug output for guest and authenticated routes.
    rag_enabled : bool
        Enables vector-based retrieval for prompt context.
    use_openai_embedding : bool
        Use OpenAI embeddings when True, otherwise local model.
    allowed_origins : List[str]
        CORS allowlist.
    chroma_data_path : str
        Filesystem path for persistent ChromaDB storage.
    figures_ingest_hash_path : Optional[str]
        Path to figures seed hash file for idempotent ingest.
    figures_seed_csv_path : Optional[str]
        Path to figures seed CSV file for initial ingest.
    """

    access_token_expire_minutes: int
    secret_key: str
    openai_api_key: Optional[str]
    openrouter_api_key: Optional[str]
    render: bool
    guest_prompt_debug: bool
    rag_enabled: bool
    use_openai_embedding: bool
    allowed_origins: List[str]
    chroma_data_path: str
    figures_ingest_hash_path: Optional[str]
    figures_seed_csv_path: Optional[str]
    safety_enabled: bool
    enable_figure_ingest: bool
    # Email + verification settings
    REQUIRE_VERIFIED_EMAIL_FOR_LOGIN: bool = False
    EMAIL_FROM: Optional[str] = None
    EMAIL_VERIFICATION_SECRET: str = "changeme-email-secret"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    EMAIL_ENABLED: bool = False
    FRONTEND_BASE_URL: Optional[str] = None

    def validate(self) -> None:
        """
        Validate required settings and cross-field constraints.

        Raises
        ------
        ValueError
            If required fields are missing or constraints are violated.
        """
        if not self.secret_key or len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be set and at least 32 characters long.")
        if self.access_token_expire_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer.")
        if not (self.openai_api_key or self.openrouter_api_key):
            raise ValueError("Set at least one of OPENAI_API_KEY or OPENROUTER_API_KEY.")


_settings: Optional[Settings] = None


def _default_allowed_origins() -> List[str]:
    """
    Provide default CORS origins for local and deployed static hosts.

    Returns
    -------
    list[str]
        Default allowed origins.
    """
    return [
        "http://localhost:8000",
        "https://places-in-time-chatbot.onrender.com",
        "https://places-in-time-history-chat.onrender.com",
    ]


def _resolve_chroma_path(render: bool) -> str:
    """
    Resolve a persistent ChromaDB data path for local or Render.

    Parameters
    ----------
    render : bool
        Whether the service is running on Render.

    Returns
    -------
    str
        Filesystem path for ChromaDB storage.
    """
    if render:
        return "/data/chroma_db"
    base = Path(__file__).resolve().parents[2] / "data" / "chroma_db"
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def _load_settings() -> Settings:
    """
    Load and validate settings from environment variables.

    Returns
    -------
    Settings
        The validated settings instance.
    """
    load_dotenv(override=False)

    access_token_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "0") or "0")
    render = _to_bool(os.getenv("RENDER"))
    allowed_raw = os.getenv("ALLOWED_ORIGINS", "")
    allowed = [o.strip() for o in allowed_raw.split(",") if o.strip()] or _default_allowed_origins()

    settings = Settings(
        access_token_expire_minutes=access_token_expire,
        secret_key=os.getenv("SECRET_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        render=render,
        guest_prompt_debug=_to_bool(os.getenv("GUEST_PROMPT_DEBUG") or os.getenv("PROMPT_DEBUG")),
        rag_enabled=_to_bool(os.getenv("RAG_ENABLED", "true")),
        use_openai_embedding=_to_bool(os.getenv("USE_OPENAI_EMBEDDING")),
        allowed_origins=allowed,
        chroma_data_path=os.getenv("CHROMA_DATA_PATH", "/data/chroma" if render else _resolve_chroma_path(render)),
        figures_ingest_hash_path=os.getenv("FIGURES_INGEST_HASH_PATH"),
        figures_seed_csv_path=os.getenv("FIGURES_SEED_CSV_PATH"),
        safety_enabled=_to_bool(os.getenv("SAFETY_ENABLED")),
        enable_figure_ingest=_to_bool(os.getenv("ENABLE_FIGURE_INGEST", "true")),
        REQUIRE_VERIFIED_EMAIL_FOR_LOGIN=_to_bool(os.getenv("REQUIRE_VERIFIED_EMAIL_FOR_LOGIN")),
        EMAIL_FROM=os.getenv("EMAIL_FROM"),
        EMAIL_VERIFICATION_SECRET=os.getenv("EMAIL_VERIFICATION_SECRET", "changeme-email-secret"),
        SMTP_HOST=os.getenv("SMTP_HOST"),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587") or "587"),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME"),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD"),
        SMTP_USE_TLS=_to_bool(os.getenv("SMTP_USE_TLS", "true")),
        EMAIL_ENABLED=_to_bool(os.getenv("EMAIL_ENABLED")),
        FRONTEND_BASE_URL=os.getenv("FRONTEND_BASE_URL") or os.getenv("PUBLIC_BASE_URL"),
    )
    settings.validate()
    return settings


def get_settings() -> Settings:
    """
    Return a cached settings instance.

    Returns
    -------
    Settings
        The validated settings object.
    """
    global _settings
    if _settings is None:
        _settings = _load_settings()
    return _settings
