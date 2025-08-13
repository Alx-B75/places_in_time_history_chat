"""Search function for retrieving relevant context chunks from ChromaDB."""

from app.vector.chroma_client import get_figure_context_collection
from app.vector.embedding_provider import get_embedding


def search_figure_context(query: str, figure_slug: str, top_k: int = 5) -> list[dict]:
    """
    Search Chroma vector store for relevant context related to a historical figure.

    Args:
        query (str): The user's message or question.
        figure_slug (str): Slug for the historical figure to filter context.
        top_k (int): Number of top results to return.

    Returns:
        List[dict]: Relevant documents with their content and metadata.
    """
    collection = get_figure_context_collection()
    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        where={"figure_slug": figure_slug},
        n_results=top_k
    )

    return [
        {
            "content": doc,
            "metadata": meta
        }
        for doc, meta in
        zip(results.get("documents", [[]])[0], results.get("metadatas", [[]])[0])
    ]
