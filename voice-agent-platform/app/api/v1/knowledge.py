import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.flags import FlagResolver
from app.db import get_db
from app.dependencies import get_current_tenant, get_tenant_flags
from app.models.knowledge import KnowledgeDoc
from app.models.tenant import Tenant
from app.schemas.knowledge import KnowledgeListResponse, KnowledgeUploadResponse
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["knowledge"])

EXTRACTORS = {
    "pdf": "_extract_pdf",
    "docx": "_extract_docx",
    "txt": "_extract_txt",
}


def _extract_pdf(content: bytes) -> str:
    import fitz

    try:
        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as exc:
        log.error("pdf_extraction_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse PDF: {exc}",
        ) from exc


def _extract_docx(content: bytes) -> str:
    import io

    from docx import Document

    try:
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        log.error("docx_extraction_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse DOCX: {exc}",
        ) from exc


def _extract_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


@router.get("", response_model=KnowledgeListResponse)
async def list_documents(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> KnowledgeListResponse:
    base = select(KnowledgeDoc).where(KnowledgeDoc.tenant_id == tenant.id)
    count_q = (
        select(func.count()).select_from(KnowledgeDoc).where(KnowledgeDoc.tenant_id == tenant.id)
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = (
        base.order_by(KnowledgeDoc.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    docs = result.scalars().all()

    return KnowledgeListResponse(
        documents=[
            KnowledgeUploadResponse(
                doc_id=str(d.id),
                filename=d.filename,
                status=d.status,
                message="",
            )
            for d in docs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/upload", response_model=KnowledgeUploadResponse, status_code=202)
async def upload_document(
    file: UploadFile,
    tenant: Tenant = Depends(get_current_tenant),
    flags: FlagResolver = Depends(get_tenant_flags),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeUploadResponse:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    allowed = flags.get("FLAG_DATA_KB_FILE_TYPES", ["pdf", "docx", "txt"])
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {ext}. Allowed: {allowed}",
        )

    content = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.max_upload_size_mb} MB",
        )

    if ext == "pdf":
        text = _extract_pdf(content)
    elif ext == "docx":
        text = _extract_docx(content)
    else:
        text = _extract_txt(content)

    doc = KnowledgeDoc(
        tenant_id=tenant.id,
        filename=file.filename,
        file_type=ext,
        status="processing",
        raw_text=text,
    )
    db.add(doc)
    await db.flush()

    try:
        from workers.tasks.kb_ingestion import ingest_document

        ingest_document.delay(str(tenant.id), str(doc.id), text)
    except Exception:
        pass  # Celery worker may not be available in dev

    return KnowledgeUploadResponse(
        doc_id=str(doc.id),
        filename=file.filename,
        status="processing",
        message="Document accepted for processing.",
    )


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(KnowledgeDoc).where(
            KnowledgeDoc.id == doc_id,
            KnowledgeDoc.tenant_id == tenant.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.delete(doc)
