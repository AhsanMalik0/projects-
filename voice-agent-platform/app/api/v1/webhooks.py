import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_tenant
from app.models.tenant import Tenant
from app.models.webhook import WebhookRegistration
from app.schemas.webhooks import WebhookRegisterRequest, WebhookResponse

router = APIRouter(tags=["webhooks"])


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookResponse]:
    result = await db.execute(
        select(WebhookRegistration).where(WebhookRegistration.tenant_id == tenant.id)
    )
    webhooks = result.scalars().all()
    return [
        WebhookResponse(
            id=str(wh.id),
            url=wh.url,
            events=wh.events,
            is_active=wh.is_active,
        )
        for wh in webhooks
    ]


@router.post("/register", response_model=WebhookResponse, status_code=201)
async def register_webhook(
    body: WebhookRegisterRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    webhook_secret = secrets.token_urlsafe(32)

    webhook = WebhookRegistration(
        tenant_id=tenant.id,
        url=body.url,
        secret=webhook_secret,
        events=body.events,
        is_active=True,
    )
    db.add(webhook)
    await db.flush()

    return WebhookResponse(
        id=str(webhook.id),
        url=webhook.url,
        events=webhook.events,
        is_active=True,
        webhook_secret=webhook_secret,
    )


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(WebhookRegistration).where(
            WebhookRegistration.id == webhook_id,
            WebhookRegistration.tenant_id == tenant.id,
        )
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    await db.delete(webhook)
