"""
EmbeddingClient: Unified adapter for text embeddings.
Supports OpenAI, OpenRouter, and local SentenceTransformer providers.
"""


import logging
import os
from typing import List, Optional
from openai import OpenAI
from app.settings import get_settings

_DIMENSIONS = {"local": 384, "openai": 1536}
_LOCAL_MODEL = "all-MiniLM-L6-v2"
_OPENAI_MODEL = "text-embedding-3-small"

# --- A/B toggling stub ---
ARM_A = "A"
ARM_B = "B"
def get_ab_arm(user_id: str = None) -> str:
    """
    Sticky bucketing placeholder for A/B toggling.
    Returns ARM_A or ARM_B. Replace with real bucketing logic as needed.
    """
    # Example: hash user_id for sticky assignment
    if user_id:
        return ARM_A if hash(user_id) % 2 == 0 else ARM_B
    # Default: random or env var
    return os.getenv("EMBEDDING_ARM", ARM_A)

class EmbeddingClient:
    def __init__(self):
        self.settings = get_settings()
        # Prefer OpenAI when an API key is configured unless explicitly disabled
        self.provider = "openai" if (self.settings.use_openai_embedding or bool(self.settings.openai_api_key)) else "local"
        self.client: Optional[object] = None
        self._init_client()

    def _init_client(self):
        if self.provider == "openai":
            try:
                self.client = OpenAI(api_key=self.settings.openai_api_key)
                return
            except Exception:
                self.client = None
                # fallback to local if OpenAI init fails
                self.provider = "local"
        # Local provider path (lazy import to avoid hard dependency)
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self.client = SentenceTransformer(_LOCAL_MODEL)
        except Exception:
            self.client = None
            # If local not available and OpenAI key exists, fallback to OpenAI
            if self.settings.openai_api_key:
                try:
                    self.provider = "openai"
                    self.client = OpenAI(api_key=self.settings.openai_api_key)
                except Exception:
                    self.client = None

    def get_embedding_dimension(self) -> int:
        return _DIMENSIONS[self.provider]

    def get_embedding(self, text: str, user_id: str = None) -> List[float]:
        if not isinstance(text, str) or not text.strip():
            return [0.0] * self.get_embedding_dimension()
        arm = get_ab_arm(user_id)
        try:
            if self.provider == "openai" and isinstance(self.client, OpenAI):
                response = self.client.embeddings.create(
                    input=text.replace("\n", " "),
                    model=_OPENAI_MODEL,
                )
                embedding = response.data[0].embedding
                usage = getattr(response, "usage", {})
                logging.info(
                    "Embedding call provider=%s model=%s arm=%s token_usage=%s",
                    self.provider, _OPENAI_MODEL, arm, usage
                )
                return embedding
            # Local embedding if sentence_transformers is available
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                if isinstance(self.client, SentenceTransformer):
                    embedding = self.client.encode(text, convert_to_tensor=False).tolist()
                else:
                    embedding = [0.0] * _DIMENSIONS.get("local", 384)
            except Exception:
                embedding = [0.0] * _DIMENSIONS.get("local", 384)
                logging.info(
                    "Embedding call provider=%s model=%s arm=%s token_usage=N/A",
                    self.provider, _LOCAL_MODEL, arm
                )
                return embedding
            logging.info(
                "Embedding call provider=%s model=%s arm=%s token_usage=0 (fallback)",
                self.provider, "unknown", arm
            )
            return [0.0] * self.get_embedding_dimension()
        except Exception as e:
            logging.error(
                "Embedding call failed provider=%s model=%s arm=%s error=%s",
                self.provider, _OPENAI_MODEL if self.provider == "openai" else _LOCAL_MODEL, arm, str(e)
            )
            return [0.0] * self.get_embedding_dimension()
