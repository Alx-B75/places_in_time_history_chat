"""
ChromaDB client setup for persistent storage of historical figure context vectors.

This module initializes a persistent Chroma client and exposes a helper to
obtain the collection used for figure context documents.
"""

from __future__ import annotations

from typing import Any

import chromadb

from app.settings import get_settings


_COLLECTION_NAME = "figure_context_collection"
_client: Any = None


def _get_client() -> chromadb.PersistentClient:
    """
    Return a singleton persistent Chroma client.

    Returns
    -------
    chromadb.PersistentClient
        Persistent client instance.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = chromadb.PersistentClient(path=settings.chroma_data_path)
    return _client


def get_figure_context_collection():
    """
    Return the persistent collection for figure context vectors.

    Returns
    -------
    chromadb.api.models.Collection.Collection
        The collection instance for figure contexts.
    """
    client = _get_client()
    return client.get_or_create_collection(name=_COLLECTION_NAME)
