from app.services.embedding.gemini import GeminiEmbedder
from app.services.vector_db.base import VectorDBProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class RAGEngine:
    def __init__(self, vector_db: VectorDBProvider | None = None) -> None:
        self.db = vector_db

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 5,
        score_threshold: float = 0.72,
    ) -> list[str]:
        if not self.db:
            return []

        embedder = GeminiEmbedder()
        query_vector = embedder.embed_one(query, task_type="RETRIEVAL_QUERY")

        results = await self.db.query(
            namespace=tenant_id,
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )

        chunks = [
            m["metadata"]["chunk"]
            for m in results.get("matches", [])
            if m.get("score", 0) >= score_threshold
        ]

        log.info(
            "rag_retrieval",
            tenant_id=tenant_id,
            query_len=len(query),
            results_count=len(chunks),
            top_k=top_k,
        )

        return chunks
