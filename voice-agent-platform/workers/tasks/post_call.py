import asyncio
import json

from google import genai

from sqlalchemy import select

from app.config import get_settings
from app.core.flags import FlagResolver
from app.core.summariser import build_postcall_prompt
from app.db import async_session_factory
from app.models.call import Call
from app.models.webhook import WebhookRegistration
from app.services.webhook import deliver_webhook
from app.utils.logging import get_logger
from workers.celery_app import celery_app

log = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_post_call(
    self,  # type: ignore[no-untyped-def]
    call_id: str,
    transcript: str,
    tenant_flags: dict,
) -> dict | None:
    try:
        settings = get_settings()
        flags = FlagResolver(tenant_id="", overrides=tenant_flags)
        prompt = build_postcall_prompt(transcript, flags)

        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.llm_model or "gemini-2.0-flash",
            contents=prompt,
        )

        raw_text = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        result = json.loads(raw_text)
        log.info("post_call_result", call_id=call_id, keys=list(result.keys()))

        store_post_call_result.delay(call_id, result)

        if flags.enabled("FLAG_OUTPUT_WEBHOOK_POSTCALL"):
            push_webhook.delay(call_id, result)

        return result
    except Exception as exc:
        log.error("post_call_error", call_id=call_id, error=str(exc))
        raise self.retry(exc=exc, countdown=90)


@celery_app.task(bind=True, max_retries=3)
def store_post_call_result(
    self,  # type: ignore[no-untyped-def]
    call_id: str,
    result: dict,
) -> None:
    async def _store() -> None:
        async with async_session_factory() as session:
            stmt = select(Call).where(Call.id == call_id)
            row = await session.execute(stmt)
            call = row.scalar_one_or_none()
            if not call:
                log.error("store_post_call_not_found", call_id=call_id)
                return
            call.summary = result.get("summary")
            call.key_points = result.get("key_points")
            call.entities = result.get("entities")
            call.sentiment = result.get("sentiment")
            call.escalation_flagged = (
                result.get("escalation", {}).get("requested", False)
                if isinstance(result.get("escalation"), dict)
                else bool(result.get("escalation"))
            )
            session.add(call)
            await session.commit()
            log.info("store_post_call_saved", call_id=call_id)

    try:
        asyncio.run(_store())
    except Exception as exc:
        log.error("store_post_call_error", call_id=call_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    bind=True,
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=480,
    retry_jitter=True,
)
def push_webhook(
    self,  # type: ignore[no-untyped-def]
    call_id: str,
    result: dict,
) -> None:
    async def _push() -> None:
        async with async_session_factory() as session:
            stmt = select(Call).where(Call.id == call_id)
            row = await session.execute(stmt)
            call = row.scalar_one_or_none()
            if not call:
                log.error("push_webhook_call_not_found", call_id=call_id)
                return

            wh_stmt = select(WebhookRegistration).where(
                WebhookRegistration.tenant_id == call.tenant_id,
                WebhookRegistration.is_active.is_(True),
            )
            wh_rows = await session.execute(wh_stmt)
            webhooks = wh_rows.scalars().all()

            payload = {
                "event": "call.completed",
                "call_id": str(call.id),
                "tenant_id": str(call.tenant_id),
                "data": result,
            }
            for wh in webhooks:
                ok = await deliver_webhook(wh.url, payload, wh.secret)
                log.info(
                    "push_webhook_result",
                    call_id=call_id,
                    webhook_id=str(wh.id),
                    success=ok,
                )

    try:
        asyncio.run(_push())
    except Exception as exc:
        log.error("push_webhook_error", call_id=call_id, error=str(exc))
        raise