import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_factory
from app.utils.logging import get_logger
from workers.celery_app import celery_app

log = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_lead_alert(
    self,
    call_id: str,
    campaign_id: str,
    contact_id: str | None,
    result: dict,
    trigger_phrase: str | None = None,
) -> None:
    """Create a marketing_alerts record and deliver it via all configured channels."""
    try:
        asyncio.run(
            _process_lead_alert(
                call_id=call_id,
                campaign_id=campaign_id,
                contact_id=contact_id,
                result=result,
                trigger_phrase=trigger_phrase,
            )
        )
    except Exception as exc:
        log.error("lead_alert_error", call_id=call_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _process_lead_alert(
    call_id: str,
    campaign_id: str,
    contact_id: str | None,
    result: dict,
    trigger_phrase: str | None,
) -> None:
    import uuid
    from app.models.call import Call

    interest_score: int = result.get("interest_score", 0) or 0
    summary: str = result.get("summary", "")

    async with async_session_factory() as session:
        # Load call for tenant_id
        call_row = await session.execute(select(Call).where(Call.id == call_id))
        call = call_row.scalar_one_or_none()
        if not call:
            log.error("lead_alert_call_not_found", call_id=call_id)
            return

        tenant_id = str(call.tenant_id)

        # Load tenant for alert settings
        from app.models.tenant import Tenant
        tenant_row = await session.execute(
            select(Tenant).where(Tenant.id == call.tenant_id)
        )
        tenant = tenant_row.scalar_one_or_none()
        if not tenant:
            log.error("lead_alert_tenant_not_found", tenant_id=tenant_id)
            return

        # Check interest score meets threshold
        min_score: int = getattr(tenant, "alert_min_score", 6) or 6
        if interest_score < min_score:
            log.info(
                "lead_alert_below_threshold",
                score=interest_score,
                threshold=min_score,
                call_id=call_id,
            )
            return

        # Load contact for customer details
        contact_name = "Unknown Customer"
        contact_phone = ""
        if contact_id:
            try:
                from app.models.contact import Contact  # type: ignore[attr-defined]
                contact_row = await session.execute(
                    select(Contact).where(Contact.id == uuid.UUID(contact_id))
                )
                contact = contact_row.scalar_one_or_none()
                if contact:
                    contact_name = contact.name or contact_phone or "Unknown Customer"
                    contact_phone = contact.phone_number or ""
                    # Mark contact as lead
                    contact.is_lead = True
                    contact.interest_score = interest_score
                    contact.status = "completed"
                    session.add(contact)
            except Exception as exc:
                log.warning("lead_alert_contact_load_error", error=str(exc))

        # Update campaign.leads_generated counter
        if campaign_id:
            try:
                from app.models.campaign import Campaign  # type: ignore[attr-defined]
                camp_row = await session.execute(
                    select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
                )
                campaign = camp_row.scalar_one_or_none()
                if campaign:
                    campaign.leads_generated = (campaign.leads_generated or 0) + 1
                    session.add(campaign)
            except Exception as exc:
                log.warning("lead_alert_campaign_update_error", error=str(exc))

        # Create marketing_alerts record if model exists
        alert_id = str(uuid.uuid4())
        delivered_via: list[str] = []
        delivery_status = "pending"

        try:
            from app.models.marketing_alert import MarketingAlert  # type: ignore[attr-defined]
            alert = MarketingAlert(
                id=uuid.UUID(alert_id),
                tenant_id=call.tenant_id,
                campaign_id=uuid.UUID(campaign_id) if campaign_id else None,
                contact_id=uuid.UUID(contact_id) if contact_id else None,
                call_id=uuid.UUID(call_id),
                trigger_phrase=trigger_phrase or "",
                interest_score=interest_score,
                summary=summary,
                delivery_status="pending",
                delivered_via=[],
            )
            session.add(alert)
        except Exception as exc:
            log.warning("lead_alert_model_not_found", error=str(exc))

        await session.commit()

    # ── Deliver alert to all configured channels ──────────────────────
    settings = get_settings()

    alert_payload = {
        "alert_id": alert_id,
        "call_id": call_id,
        "campaign_id": campaign_id,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "interest_score": interest_score,
        "trigger_phrase": trigger_phrase or "",
        "summary": summary,
        "key_points": result.get("key_points", []),
    }

    alert_email = getattr(tenant, "alert_email", None) or getattr(settings, "alert_email", None)
    slack_webhook = getattr(tenant, "alert_slack_webhook", None)

    if alert_email:
        _send_email_alert(alert_email, alert_payload)
        delivered_via.append("email")

    if slack_webhook:
        _send_slack_alert(slack_webhook, alert_payload)
        delivered_via.append("slack")

    delivery_status = "sent" if delivered_via else "no_channels_configured"
    log.info(
        "lead_alert_delivered",
        call_id=call_id,
        channels=delivered_via,
        status=delivery_status,
    )


def _send_email_alert(to_email: str, payload: dict) -> None:
    """Send formatted HTML hot-lead email. Uses app/utils/email.py when available."""
    try:
        from app.utils.email import send_lead_alert_email  # type: ignore[import]
        send_lead_alert_email(to_email, payload)
    except ImportError:
        # email.py not yet built — log for now
        log.info("lead_alert_email_stub", to=to_email, score=payload.get("interest_score"))
    except Exception as exc:
        log.error("lead_alert_email_error", to=to_email, error=str(exc))


def _send_slack_alert(webhook_url: str, payload: dict) -> None:
    """Post Block Kit Slack message. Uses app/utils/slack.py when available."""
    try:
        from app.utils.slack import send_lead_alert_slack  # type: ignore[import]
        send_lead_alert_slack(webhook_url, payload)
    except ImportError:
        log.info("lead_alert_slack_stub", score=payload.get("interest_score"))
    except Exception as exc:
        log.error("lead_alert_slack_error", error=str(exc))