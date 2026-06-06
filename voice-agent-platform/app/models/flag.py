import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TenantFlag(Base):
    __tablename__ = "tenant_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    flag_key: Mapped[str] = mapped_column(String(120), nullable=False)
    flag_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    set_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @classmethod
    async def get_all(cls, tenant_id: str, db: AsyncSession) -> list["TenantFlag"]:
        result = await db.execute(select(cls).where(cls.tenant_id == tenant_id))
        return list(result.scalars().all())

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "flag_key": self.flag_key,
            "flag_value": self.flag_value,
            "set_by": self.set_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
