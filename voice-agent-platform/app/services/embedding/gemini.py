import time
from typing import Literal

from google import genai
from google.genai import types

from app.config import get_settings
from app.utils.logging import get_logger

log = get_logger(__name__)

# Gemini embedding model — 768 dimensions
GEMINI_EMBED_MODEL = "text-embedding-004"
GEMINI_EMBED_DIM = 768


class GeminiEmbedder:
    """Generates embeddings using Google's text-embedding-004 model (768-dim)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = GEMINI_EMBED_MODEL

    def embed_one(
        self,
        text: str,
        task_type: Literal[
            "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY", "CLASSIFICATION"
        ] = "RETRIEVAL_QUERY",
    ) -> list[float]:
        """Embed a single string."""
        start = time.monotonic()

        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        vector = result.embeddings[0].values

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info("gemini_embed_one", latency_ms=round(elapsed_ms, 2), dims=len(vector))
        return vector

    def embed_batch(
        self,
        texts: list[str],
        task_type: Literal[
            "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY", "CLASSIFICATION"
        ] = "RETRIEVAL_DOCUMENT",
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Embed a list of strings in batches."""
        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            start = time.monotonic()

            result = self.client.models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            vectors = [e.values for e in result.embeddings]
            all_vectors.extend(vectors)

            elapsed_ms = (time.monotonic() - start) * 1000
            log.info(
                "gemini_embed_batch",
                latency_ms=round(elapsed_ms, 2),
                batch_size=len(batch),
                total_so_far=len(all_vectors),
            )

        return all_vectors
