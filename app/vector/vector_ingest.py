"""Ingests all figure context entries from the database into the Chroma vector store."""

import os
import sys

# --- Adjust path for script-based execution ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from app.models import FigureContext
from app.figures_database import FigureSessionLocal
from app.vector.chroma_client import get_figure_context_collection
from app.vector.embedding_provider import get_embedding


def ingest_all_context_chunks():
    """
    Embeds all FigureContext entries from the database and stores them in Chroma,
    associating each embedding with the correct figure_slug.
    """
    session = FigureSessionLocal()
    collection = get_figure_context_collection()
    count = 0

    try:
        contexts = session.query(FigureContext).all()
        for ctx in contexts:
            if ctx.content:
                embedding = get_embedding(ctx.content)
                collection.add(
                    documents=[ctx.content],
                    embeddings=[embedding],
                    metadatas=[{"figure_slug": ctx.figure_slug}],
                    ids=[f"{ctx.figure_slug}-{ctx.id}"]
                )
                count += 1
        print(f"✅ Ingested {count} context chunks into Chroma.")
    finally:
        session.close()


if __name__ == "__main__":
    ingest_all_context_chunks()
