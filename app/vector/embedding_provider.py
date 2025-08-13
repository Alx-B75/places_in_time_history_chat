"""Embedding provider for generating vector representations using OpenAI or local models."""

import os
from typing import List

from openai import OpenAI
from sentence_transformers import SentenceTransformer

# --- Provider Configuration ---
USE_OPENAI = os.getenv("USE_OPENAI_EMBEDDING", "false").lower() == "true"

MODEL_CONFIG = {
    "local": {
        "model_name": "all-MiniLM-L6-v2",
        "dimension": 384,
    },
    "openai": {
        "model_name": "text-embedding-3-small",
        "dimension": 1536,
    },
}

provider_key = "openai" if USE_OPENAI else "local"

# --- Initialize Embedding Client ---
client = None
try:
    if USE_OPENAI:
        client = OpenAI()
    else:
        client = SentenceTransformer(MODEL_CONFIG["local"]["model_name"])
except Exception:
    client = None


def get_embedding_dimension() -> int:
    """
    Return the embedding vector dimension for the current provider.

    Returns:
        int: Embedding size (e.g., 384 for local, 1536 for OpenAI).
    """
    return MODEL_CONFIG[provider_key]["dimension"]


def get_embedding(text: str) -> List[float]:
    """
    Generate an embedding for the given input text.

    Args:
        text (str): Input string to embed.

    Returns:
        List[float]: The embedding vector or a zero-vector on failure.
    """
    if not client or not isinstance(text, str) or not text.strip():
        return [0.0] * get_embedding_dimension()

    try:
        if USE_OPENAI:
            response = client.embeddings.create(
                input=text.replace("\n", " "),
                model=MODEL_CONFIG["openai"]["model_name"]
            )
            return response.data[0].embedding
        return client.encode(text, convert_to_tensor=False).tolist()
    except Exception:
        return [0.0] * get_embedding_dimension()
