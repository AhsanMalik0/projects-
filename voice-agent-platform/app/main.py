from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import admin, calls, knowledge, onboarding, webhooks
from app.api.v1 import voice as voice_ws
from app.config import get_settings
from app.db import Base, engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)

    app = FastAPI(
        title="AI Voice Agent API",
        version="1.0.0",
        description="AI Voice Call Agent Platform",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_per_minute,
    )

    # Prometheus metrics
    Instrumentator(
        should_group_status_codes=True,
        should_instrument_requests_inprogress=True,
    ).instrument(app).expose(app, endpoint="/metrics")

    app.include_router(onboarding.router, prefix="/api/v1/onboarding")
    app.include_router(calls.router, prefix="/api/v1/calls")
    app.include_router(knowledge.router, prefix="/api/v1/knowledge")
    app.include_router(webhooks.router, prefix="/api/v1/webhooks")
    app.include_router(admin.router, prefix="/api/v1/admin")
    app.include_router(voice_ws.router, prefix="/api/v1/voice")

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": "1.0.0"}

    return app


app = create_app()
