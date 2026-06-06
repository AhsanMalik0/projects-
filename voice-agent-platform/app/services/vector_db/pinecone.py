from typing import Any

from pinecone import Pinecone

from app.config import get_settings
from app.services.vector_db.base import VectorDBProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class PineconeVectorDB(VectorDBProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self.pc.Index(settings.pinecone_index_name)

    async def upsert(self, namespace: str, records: list[dict[str, Any]]) -> None:
        vectors = [(r["id"], r["values"], r.get("metadata", {})) for r in records]
        self.index.upsert(vectors=vectors, namespace=namespace)
        log.info("pinecone_upsert", namespace=namespace, count=len(vectors))

    async def query(
        self,
        namespace: str,
        vector: list[float],
        top_k: int = 5,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        result = self.index.query(
            namespace=namespace,
            vector=vector,
            top_k=top_k,
            include_metadata=include_metadata,
        )
        matches = [
            {
                "id": m["id"],
                "score": m["score"],
                "metadata": m.get("metadata", {}),
            }
            for m in result.get("matches", [])
        ]
        return {"matches": matches}

    async def delete(self, namespace: str, ids: list[str]) -> None:
        self.index.delete(ids=ids, namespace=namespace)
        log.info("pinecone_delete", namespace=namespace, count=len(ids))
