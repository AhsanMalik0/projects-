import asyncio
from datetime import UTC, datetime, time as dtime

from app.db import async_session_factory
from app.utils.logging import get_logger
from workers.celery_app import celery_app

log = get_logger(__name__)


@celery_app.task(bind=True, max_retries=0)  # Retries managed manually below
def dial_contact(self, campaign_id: str, contact_id: str) -> dict:
    """Dial one contact for a campaign.

    1. Validates campaign is still running and contact is still pending.
    2. Checks daily call window (time of day).
    3. Loads tenant telephony credentials.
    4. Places the call via the configured provider.
    5. Updates contact and campaign counters.
    6. Schedules retry if not answered (up to campaign.retry_attempts).
    """
    try:
        return asyncio.run(_dial(campaign_id, contact_id))
    except Exception as exc:
        log.error("dial_contact_error", campaign_id=campaign_id,
                  contact_id=contact_id, error=str(exc))
        return {"error": str(exc)}


async def _dial(campaign_id: str, contact_id: str) -> dict:
    import uuid
    from sqlalchemy import select

    from app.config import get_settings
    from app.models.call import Call
    from app.utils.crypto import decrypt_text

    settings = get_settings()

    async with async_session_factory() as session:
        from app.models.campaign import Campaign  # type: ignore[attr-defined]
        from app.models.contact import Contact  # type: ignore[attr-defined]
        from app.models.tenant import Tenant

        # ── Load records ──────────────────────────────────────────────
        camp_row = await session.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        )
        campaign = camp_row.scalar_one_or_none()
        if not campaign:
            return {"skipped": "campaign_not_found"}

        if campaign.status != "running":
            return {"skipped": f"campaign_status:{campaign.status}"}

        contact_row = await session.execute(
            select(Contact).where(Contact.id == uuid.UUID(contact_id))
        )
        contact = contact_row.scalar_one_or_none()
        if not contact:
            return {"skipped": "contact_not_found"}

        if contact.status != "pending":
            return {"skipped": f"contact_status:{contact.status}"}

        tenant_row = await session.execute(
            select(Tenant).where(Tenant.id == campaign.tenant_id)
        )
        tenant = tenant_row.scalar_one_or_none()
        if not tenant:
            return {"skipped": "tenant_not_found"}

        # ── Check daily call window ───────────────────────────────────
        window = campaign.daily_call_window or {}
        if window and not _in_call_window(window):
            # Requeue for next window open (try again in 30 min)
            dial_contact.apply_async(
                kwargs={"campaign_id": campaign_id, "contact_id": contact_id},
                countdown=1800,
            )
            log.info("dial_outside_window", contact_id=contact_id)
            return {"requeued": "outside_window"}

        # ── Load telephony credentials ────────────────────────────────
        provider_name = getattr(tenant, "telephony_provider", None) or "twilio"
        raw_sid = getattr(tenant, "telephony_account_sid", None) or settings.twilio_account_sid
        raw_token = getattr(tenant, "telephony_auth_token", None) or settings.twilio_auth_token
        phone_number = getattr(tenant, "telephony_phone_number", None) or settings.twilio_phone_number

        # Decrypt if stored encrypted
        try:
            account_sid = decrypt_text(raw_sid) if raw_sid else ""
            auth_token = decrypt_text(raw_token) if raw_token else ""
        except Exception:
            account_sid = raw_sid or ""
            auth_token = raw_token or ""

        if not account_sid or not auth_token or not phone_number:
            log.error("dial_missing_telephony_creds", tenant_id=str(tenant.id))
            contact.status = "failed"
            session.add(contact)
            await session.commit()
            return {"error": "missing_telephony_credentials"}

        # ── Build webhook URL with full context ───────────────────────
        # voice.py uses these params to load PromptBuilder context
        api_key = getattr(tenant, "api_key", None) or ""
        webhook_url = (
            f"{settings.base_url}/api/v1/voice/stream"
            f"?api_key={api_key}"
            f"&campaign_id={campaign_id}"
            f"&contact_id={contact_id}"
        )

        # ── Place the call ────────────────────────────────────────────
        from app.services.telephony.base import get_telephony_provider
        telephony = get_telephony_provider(
            provider_name=provider_name,
            account_sid=account_sid,
            auth_token=auth_token,
            phone_number=phone_number,
        )

        # Create Call record before dialling
        call = Call(
            tenant_id=tenant.id,
            to_number=contact.phone_number,
            status="initiated",
        )
        try:
            call.campaign_id = uuid.UUID(campaign_id)
            call.contact_id = uuid.UUID(contact_id)
        except (AttributeError, ValueError):
            pass
        session.add(call)
        await session.flush()
        call_id = str(call.id)

        # Update contact status
        contact.status = "calling"
        contact.attempts = (contact.attempts or 0) + 1
        contact.last_called_at = datetime.now(UTC)
        contact.call_id = call.id
        session.add(contact)

        # Update campaign counter
        campaign.calls_made = (campaign.calls_made or 0) + 1
        session.add(campaign)

        await session.commit()
        log.info("dial_placing_call", contact_id=contact_id, call_id=call_id,
                 provider=provider_name)

        # ── Place call via telephony provider ─────────────────────────
        try:
            external_call_id = await telephony.initiate_call(
                to_number=contact.phone_number,
                webhook_url=webhook_url,
            )
            log.info("dial_call_placed", call_id=call_id, external_id=external_call_id)

            async with async_session_factory() as s2:
                from sqlalchemy import update
                await s2.execute(
                    update(Call)
                    .where(Call.id == call.id)
                    .values(status="in_progress")
                )
                await s2.commit()

            return {"call_id": call_id, "external_id": external_call_id}

        except Exception as exc:
            log.error("dial_call_failed", call_id=call_id, error=str(exc))

            # Handle retry logic
            max_retries = campaign.retry_attempts or 0
            retry_delay = (campaign.retry_delay_minutes or 30) * 60
            attempts = contact.attempts or 1

            if attempts <= max_retries:
                async with async_session_factory() as s2:
                    from sqlalchemy import update
                    await s2.execute(
                        update(Contact)
                        .where(Contact.id == uuid.UUID(contact_id))
                        .values(status="pending")
                    )
                    await s2.commit()
                dial_contact.apply_async(
                    kwargs={"campaign_id": campaign_id, "contact_id": contact_id},
                    countdown=retry_delay,
                )
                log.info("dial_retry_scheduled", contact_id=contact_id,
                         attempt=attempts, max=max_retries, delay=retry_delay)
                return {"retry_scheduled": True, "attempt": attempts}
            else:
                async with async_session_factory() as s2:
                    from sqlalchemy import update
                    await s2.execute(
                        update(Contact)
                        .where(Contact.id == uuid.UUID(contact_id))
                        .values(status="no_answer")
                    )
                    await s2.commit()
                return {"failed": "max_retries_exceeded"}


def _in_call_window(window: dict) -> bool:
    """Return True if current time is within the configured daily call window."""
    try:
        import pytz
        tz_name = window.get("timezone", "UTC")
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz).time()

        start_str = window.get("start", "09:00")
        end_str = window.get("end", "18:00")
        h, m = map(int, start_str.split(":"))
        start = dtime(h, m)
        h, m = map(int, end_str.split(":"))
        end = dtime(h, m)
        return start <= now <= end
    except Exception:
        return True  # If window check fails, allow the call