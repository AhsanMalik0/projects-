import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.flags import FlagResolver
from app.db import get_db
from app.dependencies import get_current_tenant, get_tenant_flags
from app.models.call import Call
from app.models.tenant import Tenant
from app.schemas.calls import (
    CallInitiateRequest,
    CallListResponse,
    CallResponse,
    CallStatusUpdateRequest,
    CallSummaryResponse,
)
from app.utils.crypto import encrypt_text
from app.utils.redaction import redact_pii

router = APIRouter(tags=["calls"])

VALID_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "initiated": ["in_progress", "failed", "cancelled"],
    "in_progress": ["completed", "failed"],
    "completed": [],
    "failed": [],
    "cancelled": [],
}


@router.post("/initiate", response_model=CallResponse, status_code=201)
async def initiate_call(
    body: CallInitiateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CallResponse:
    call = Call(
        tenant_id=tenant.id,
        to_number=body.to_number,
        status="initiated",
        metadata_=body.metadata,
        started_at=datetime.now(UTC),
    )
    db.add(call)
    await db.flush()

    return CallResponse(
        call_id=str(call.id),
        status="initiated",
        estimated_connect_ms=1200,
        webhook_registered=bool(tenant.webhook_url),
    )


@router.patch("/{call_id}/status")
async def update_call_status(
    call_id: uuid.UUID,
    body: CallStatusUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    flags: FlagResolver = Depends(get_tenant_flags),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    allowed = VALID_STATUS_TRANSITIONS.get(call.status, [])
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{call.status}' to '{body.status}'. Allowed: {allowed}",
        )

    call.status = body.status
    if body.status == "completed":
        call.ended_at = datetime.now(UTC)
        if call.started_at:
            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())

    if body.transcript is not None:
        transcript = body.transcript
        if flags.enabled("FLAG_DATA_GDPR_REDACTION"):
            transcript = redact_pii(transcript)
        if flags.enabled("FLAG_DATA_TRANSCRIPT_ENCRYPTION"):
            transcript = encrypt_text(transcript)
        call.transcript = transcript

    db.add(call)
    await db.flush()

    return {"call_id": str(call.id), "status": call.status}


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CallResponse:
    result = await db.execute(select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    return CallResponse(
        call_id=str(call.id),
        status=call.status,
        webhook_registered=bool(tenant.webhook_url),
    )


@router.get("/{call_id}/transcript")
async def get_transcript(
    call_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    return {
        "call_id": str(call.id),
        "transcript": call.transcript,
        "status": call.status,
    }


@router.get("/{call_id}/summary", response_model=CallSummaryResponse)
async def get_summary(
    call_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CallSummaryResponse:
    result = await db.execute(select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    return CallSummaryResponse(
        call_id=str(call.id),
        summary=call.summary,
        key_points=call.key_points,
        entities=call.entities,
        sentiment=call.sentiment,
        escalation_flagged=call.escalation_flagged,
        duration_seconds=call.duration_seconds,
    )


@router.get("", response_model=CallListResponse)
async def list_calls(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    call_status: str | None = Query(None, alias="status"),
) -> CallListResponse:
    query = select(Call).where(Call.tenant_id == tenant.id)
    count_query = select(func.count()).select_from(Call).where(Call.tenant_id == tenant.id)

    if call_status:
        query = query.where(Call.status == call_status)
        count_query = count_query.where(Call.status == call_status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Call.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    calls = result.scalars().all()

    return CallListResponse(
        calls=[
            CallResponse(
                call_id=str(c.id),
                status=c.status,
                webhook_registered=bool(tenant.webhook_url),
            )
            for c in calls
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
