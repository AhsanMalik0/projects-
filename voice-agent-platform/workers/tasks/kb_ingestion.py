import tiktoken

from app.services.embedding.gemini import GeminiEmbedder, GEMINI_EMBED_DIM
from app.utils.logging import get_logger
from workers.celery_app import celery_app

log = get_logger(__name__)

# Use cl100k_base (GPT-4 tokenizer) for chunking — works fine for any text
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def chunk_text(text: str) -> list[str]:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunks.append(enc.decode(tokens[start:end]))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


@celery_app.task(bind=True, max_retries=3)
def ingest_document(
    self,  # type: ignore[no-untyped-def]
    tenant_id: str,
    doc_id: str,
    text: str,
) -> dict:
    try:
        embedder = GeminiEmbedder()
        chunks = chunk_text(text)
        vectors = embedder.embed_batch(chunks, task_type="RETRIEVAL_DOCUMENT")

        from app.services.vector_db.pinecone import PineconeVectorDB

        db = PineconeVectorDB()
        records = [
            {
                "id": f"{doc_id}_{i}",
                "values": v,
                "metadata": {
                    "tenant_id": tenant_id,
                    "doc_id": doc_id,
                    "chunk": c,
                },
            }
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ]

        import asyncio

        asyncio.run(db.upsert(namespace=tenant_id, records=records))

        log.info(
            "kb_ingestion_complete",
            tenant_id=tenant_id,
            doc_id=doc_id,
            chunks=len(chunks),
            embed_dims=GEMINI_EMBED_DIM,
        )
        return {"doc_id": doc_id, "chunks": len(chunks), "status": "ready"}

    except Exception as exc:
        log.error("kb_ingestion_error", doc_id=doc_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)
