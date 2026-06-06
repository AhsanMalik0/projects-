import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.onboarding import (
    TenantConfigureRequest,
    TenantRegisterRequest,
    TenantRegisterResponse,
    TenantStatusResponse,
)
from app.utils.auth import generate_api_key, hash_api_key

router = APIRouter(tags=["onboarding"])


@router.post("/register", response_model=TenantRegisterResponse, status_code=201)
async def register_tenant(
    body: TenantRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TenantRegisterResponse:
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    webhook_secret = secrets.token_urlsafe(32)

    tenant = Tenant(
        name=body.name,
        industry=body.industry,
        use_case=body.use_case,
        api_key_hash=key_hash,
        status="sandbox",
        webhook_url=body.webhook_url,
        webhook_secret=webhook_secret,
    )
    db.add(tenant)
    await db.flush()

    return TenantRegisterResponse(
        tenant_id=str(tenant.id),
        api_key=api_key,
        status="sandbox",
        message="Tenant registered. Store your API key securely — it won't be shown again.",
    )


@router.post("/configure")
async def configure_tenant(
    body: TenantConfigureRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.use_case is not None:
        tenant.use_case = body.use_case
    if body.persona_prompt is not None:
        tenant.persona_prompt = body.persona_prompt
    if body.webhook_url is not None:
        tenant.webhook_url = body.webhook_url
    if body.industry is not None:
        tenant.industry = body.industry

    db.add(tenant)
    await db.flush()

    return {"status": "updated", "tenant_id": str(tenant.id)}


@router.get("/status", response_model=TenantStatusResponse)
async def get_status(
    tenant: Tenant = Depends(get_current_tenant),
) -> TenantStatusResponse:
    return TenantStatusResponse(
        tenant_id=str(tenant.id),
        name=tenant.name,
        status=tenant.status,
        use_case=tenant.use_case,
        webhook_url=tenant.webhook_url,
        created_at=tenant.created_at.isoformat() if tenant.created_at else None,
    )


@router.post("/rotate-key")
async def rotate_api_key(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    new_api_key = generate_api_key()
    tenant.api_key_hash = hash_api_key(new_api_key)
    db.add(tenant)
    await db.flush()

    return {
        "tenant_id": str(tenant.id),
        "api_key": new_api_key,
        "message": "API key rotated. Store the new key securely — it won't be shown again.",
    }
