from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.flags import DEFAULTS, FlagResolver
from app.db import get_db
from app.dependencies import get_current_tenant, get_tenant_flags
from app.models.audit import AuditLog
from app.models.flag import TenantFlag
from app.models.tenant import Tenant
from app.schemas.flags import FlagResponse, FlagUpdateRequest

router = APIRouter(tags=["admin"])


@router.get("/flags", response_model=list[FlagResponse])
async def list_flags(
    tenant: Tenant = Depends(get_current_tenant),
    flags: FlagResolver = Depends(get_tenant_flags),
    db: AsyncSession = Depends(get_db),
) -> list[FlagResponse]:
    result = await db.execute(select(TenantFlag).where(TenantFlag.tenant_id == tenant.id))
    overrides = {f.flag_key: f.flag_value for f in result.scalars().all()}

    response = []
    for key, default_value in DEFAULTS.items():
        is_overridden = key in overrides
        response.append(
            FlagResponse(
                flag_key=key,
                flag_value=overrides[key] if is_overridden else default_value,
                is_default=not is_overridden,
            )
        )
    return response


@router.patch("/flags/{flag_key}")
async def update_flag(
    flag_key: str,
    body: FlagUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    flags: FlagResolver = Depends(get_tenant_flags),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not flags.enabled("FLAG_CONTROL_TENANT_SELF_SERVE"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-serve flag management is disabled for this tenant",
        )

    if flag_key not in DEFAULTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown flag: {flag_key}",
        )

    default_val = DEFAULTS[flag_key]
    if not isinstance(body.value, type(default_val)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Flag {flag_key} expects type {type(default_val).__name__},"
                f" got {type(body.value).__name__}"
            ),
        )

    old_value = flags.get(flag_key)

    result = await db.execute(
        select(TenantFlag).where(
            TenantFlag.tenant_id == tenant.id,
            TenantFlag.flag_key == flag_key,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.flag_value = body.value
        existing.set_by = str(tenant.id)
    else:
        new_flag = TenantFlag(
            tenant_id=tenant.id,
            flag_key=flag_key,
            flag_value=body.value,
            set_by=str(tenant.id),
        )
        db.add(new_flag)

    audit = AuditLog(
        tenant_id=tenant.id,
        flag_key=flag_key,
        old_value=old_value,
        new_value=body.value,
        set_by=str(tenant.id),
    )
    db.add(audit)
    await db.flush()

    return {
        "flag_key": flag_key,
        "old_value": old_value,
        "new_value": body.value,
        "status": "updated",
    }
