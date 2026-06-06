import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.flags import FlagResolver, load_flags
from app.db import get_db
from app.models.tenant import Tenant
from app.utils.auth import hash_api_key


async def get_current_tenant(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )
    api_key = authorization[7:]
    key_hash = hash_api_key(api_key)

    result = await db.execute(select(Tenant).where(Tenant.api_key_hash == key_hash))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    if tenant.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is suspended",
        )
    return tenant


async def get_tenant_flags(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> FlagResolver:
    return await load_flags(str(tenant.id), db)


def require_tenant_id(tenant: Tenant = Depends(get_current_tenant)) -> uuid.UUID:
    return tenant.id
