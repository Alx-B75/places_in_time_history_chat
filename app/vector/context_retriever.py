"""
Vector search for historical figure context.

This module queries the Chroma collection for context documents filtered by
figure slug and returns compact records suitable for prompt assembly.
"""

from __future__ import annotations

from typing import Dict, List

from app.vector.chroma_client import get_figure_context_collection
from app.vector.embedding_provider import get_embedding


def search_figure_context(query: str, figure_slug: str, top_k: int = 5) -> List[Dict]:
    """
    Search the vector store for relevant context related to a historical figure.

    Parameters
    ----------
    query : str
        The user's message or question.
    figure_slug : str
        Slug for the historical figure to filter context.
    top_k : int
        Number of top results to return.

    Returns
    -------
    list[dict]
        Relevant documents with their content and metadata.
    """
    collection = get_figure_context_collection()
    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        where={"figure_slug": figure_slug},
        n_results=top_k,
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    return [{"content": doc, "metadata": meta} for doc, meta in zip(documents, metadatas)]
