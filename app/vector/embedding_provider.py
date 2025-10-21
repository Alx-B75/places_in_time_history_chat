"""
Embedding provider for generating vector representations.

This module supports either OpenAI embeddings or a local SentenceTransformer
model, selected via configuration.
"""

from __future__ import annotations


from typing import List
from app.services.embedding_client import EmbeddingClient
from typing import Optional

_embedding_client: Optional[EmbeddingClient] = None


def _init() -> None:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()


def get_embedding_dimension() -> int:
    global _embedding_client
    if _embedding_client is None:
        _init()
    if _embedding_client is None:
        # Defensive fallback: return OpenAI dim by default
        return 1536
    return _embedding_client.get_embedding_dimension()


def get_embedding(text: str) -> List[float]:
    global _embedding_client
    if _embedding_client is None:
        _init()
    if _embedding_client is None:
        # Defensive fallback: return zero-vector
        return [0.0] * 1536
    return _embedding_client.get_embedding(text)
