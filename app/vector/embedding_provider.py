"""
Embedding provider for generating vector representations.

This module supports either OpenAI embeddings or a local SentenceTransformer
model, selected via configuration.
"""

from __future__ import annotations

from typing import List, Optional, Union

from openai import OpenAI
from sentence_transformers import SentenceTransformer

from app.settings import get_settings


_client: Optional[Union[OpenAI, SentenceTransformer]] = None
_provider_key: Optional[str] = None
_DIMENSIONS = {"local": 384, "openai": 1536}
_LOCAL_MODEL = "all-MiniLM-L6-v2"
_OPENAI_MODEL = "text-embedding-3-small"


def _init() -> None:
    """
    Initialize the embedding client and provider selection.
    """
    global _client, _provider_key
    settings = get_settings()
    if settings.use_openai_embedding:
        try:
            _client = OpenAI(api_key=settings.openai_api_key)
            _provider_key = "openai"
            return
        except Exception:
            _client = None
            _provider_key = "openai"
            return
    try:
        _client = SentenceTransformer(_LOCAL_MODEL)
        _provider_key = "local"
    except Exception:
        _client = None
        _provider_key = "local"


def get_embedding_dimension() -> int:
    """
    Return the embedding vector dimension for the active provider.

    Returns
    -------
    int
        Embedding size for the current provider.
    """
    if _provider_key is None:
        _init()
    return _DIMENSIONS["openai" if _provider_key == "openai" else "local"]


def get_embedding(text: str) -> List[float]:
    """
    Generate an embedding for input text, or a zero-vector on failure.

    Parameters
    ----------
    text : str
        Input to embed.

    Returns
    -------
    list[float]
        Embedding vector.
    """
    if _provider_key is None:
        _init()
    if not isinstance(text, str) or not text.strip():
        return [0.0] * get_embedding_dimension()
    try:
        if _provider_key == "openai" and isinstance(_client, OpenAI):
            response = _client.embeddings.create(
                input=text.replace("\n", " "),
                model=_OPENAI_MODEL,
            )
            return response.data[0].embedding
        if isinstance(_client, SentenceTransformer):
            return _client.encode(text, convert_to_tensor=False).tolist()
        return [0.0] * get_embedding_dimension()
    except Exception:
        return [0.0] * get_embedding_dimension()
