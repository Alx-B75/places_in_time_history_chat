"""ChromaDB client setup for persistent storage of historical figure context vectors."""

import os

import chromadb

# --- Determine environment: local vs Render ---
if os.getenv("RENDER", "false").lower() == "true":
    # Render-specific path (read-write on Render)
    CHROMA_DATA_PATH = "/data/chroma_db"
else:
    # Local development path (inside project root)
    CHROMA_DATA_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma_db")
    )

# Ensure the directory exists (safe for local only)
os.makedirs(CHROMA_DATA_PATH, exist_ok=True)

# --- Constants ---
COLLECTION_NAME = "figure_context_collection"

# --- Persistent ChromaDB Client ---
client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)


def get_figure_context_collection():
    """
    Get or create the collection used for storing vectorized context entries
    tied to historical figures.

    Returns:
        chromadb.api.models.Collection.Collection: The Chroma collection object.
    """
    return client.get_or_create_collection(name=COLLECTION_NAME)
