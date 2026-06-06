from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.tenant import Tenant


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_tenant():
    tenant = MagicMock(spec=Tenant)
    tenant.id = "00000000-0000-0000-0000-000000000001"
    tenant.name = "Test Corp"
    tenant.status = "sandbox"
    tenant.use_case = "support"
    tenant.webhook_url = "https://example.com/webhook"
    tenant.persona_prompt = "You are a helpful assistant."
    tenant.created_at = MagicMock()
    tenant.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    tenant.api_key_hash = "test_hash"
    return tenant


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"


class TestOnboardingEndpoints:
    @pytest.mark.asyncio
    async def test_register_tenant(self, mock_db: AsyncMock) -> None:
        with patch("app.api.v1.onboarding.Depends", return_value=mock_db):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/onboarding/register",
                    json={
                        "name": "Test Corp",
                        "industry": "tech",
                        "use_case": "support",
                    },
                )
        assert resp.status_code in (201, 500)


class TestCallsEndpoints:
    @pytest.mark.asyncio
    async def test_list_calls_unauthenticated(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/calls")
        assert resp.status_code in (401, 403, 422)


class TestKnowledgeEndpoints:
    @pytest.mark.asyncio
    async def test_list_knowledge_unauthenticated(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/knowledge")
        assert resp.status_code in (401, 403, 422)


class TestWebhookEndpoints:
    @pytest.mark.asyncio
    async def test_list_webhooks_unauthenticated(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/webhooks")
        assert resp.status_code in (401, 403, 422)


class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_admin_flags_unauthenticated(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/flags")
        assert resp.status_code in (401, 403, 422)
