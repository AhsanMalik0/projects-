from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.services.vector_db.base import VectorDBProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class QdrantVectorDB(VectorDBProvider):
    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "voice_agent_kb",
    ) -> None:
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            # Gemini text-embedding-004 produces 768-dimensional vectors
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

    async def upsert(self, namespace: str, records: list[dict[str, Any]]) -> None:
        points = [
            PointStruct(
                id=r["id"],
                vector=r["values"],
                payload={**r.get("metadata", {}), "namespace": namespace},
            )
            for r in records
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        log.info("qdrant_upsert", namespace=namespace, count=len(points))

    async def query(
        self,
        namespace: str,
        vector: list[float],
        top_k: int = 5,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=top_k,
            query_filter=Filter(
                must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
            ),
            with_payload=include_metadata,
        )
        matches = [
            {
                "id": str(r.id),
                "score": r.score,
                "metadata": r.payload or {},
            }
            for r in results
        ]
        return {"matches": matches}

    async def delete(self, namespace: str, ids: list[str]) -> None:
        from qdrant_client.models import PointIdsList

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=ids),
        )
        log.info("qdrant_delete", namespace=namespace, count=len(ids))
