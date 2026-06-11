import asyncio
import math

from app.db import async_session_factory
from app.utils.logging import get_logger
from workers.celery_app import celery_app

log = get_logger(__name__)

# Max calls per hour to stay within Twilio/Telnyx rate limits
MAX_CALLS_PER_HOUR = 200


@celery_app.task(bind=True, max_retries=2)
def schedule_campaign(self, campaign_id: str) -> dict:
    """Load all pending contacts for a campaign and queue dial_contact tasks.

    Staggers tasks over time to respect telephony rate limits.
    Updates campaign.status = 'running'.
    """
    try:
        return asyncio.run(_schedule(campaign_id))
    except Exception as exc:
        log.error("schedule_campaign_error", campaign_id=campaign_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _schedule(campaign_id: str) -> dict:
    import uuid
    from sqlalchemy import select, update

    async with async_session_factory() as session:
        from app.models.campaign import Campaign  # type: ignore[attr-defined]
        from app.models.contact import Contact  # type: ignore[attr-defined]

        # Load campaign
        row = await session.execute(
            select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
        )
        campaign = row.scalar_one_or_none()
        if not campaign:
            log.error("schedule_campaign_not_found", campaign_id=campaign_id)
            return {"error": "campaign_not_found"}

        if campaign.status not in ("draft", "scheduled", "paused"):
            log.warning(
                "schedule_campaign_wrong_status",
                campaign_id=campaign_id,
                status=campaign.status,
            )
            return {"error": f"wrong_status:{campaign.status}"}

        # Load all pending contacts
        contacts_row = await session.execute(
            select(Contact).where(
                Contact.campaign_id == uuid.UUID(campaign_id),
                Contact.status == "pending",
            )
        )
        contacts = contacts_row.scalars().all()

        if not contacts:
            log.warning("schedule_campaign_no_contacts", campaign_id=campaign_id)
            campaign.status = "completed"
            session.add(campaign)
            await session.commit()
            return {"queued": 0}

        # Calculate stagger delay between calls (seconds)
        # Spread evenly — never exceed MAX_CALLS_PER_HOUR
        total = len(contacts)
        seconds_per_call = max(1, math.ceil(3600 / MAX_CALLS_PER_HOUR))
        log.info(
            "schedule_campaign_start",
            campaign_id=campaign_id,
            total=total,
            stagger_sec=seconds_per_call,
        )

        # Queue dial_contact for each contact with staggered countdown
        from workers.tasks.campaign_dialler import dial_contact

        for i, contact in enumerate(contacts):
            countdown = i * seconds_per_call
            dial_contact.apply_async(
                kwargs={
                    "campaign_id": campaign_id,
                    "contact_id": str(contact.id),
                },
                countdown=countdown,
            )

        # Mark campaign running
        campaign.status = "running"
        campaign.total_contacts = campaign.total_contacts or total
        session.add(campaign)
        await session.commit()

        log.info(
            "schedule_campaign_done",
            campaign_id=campaign_id,
            tasks_queued=total,
        )
        return {"queued": total, "stagger_sec": seconds_per_call}