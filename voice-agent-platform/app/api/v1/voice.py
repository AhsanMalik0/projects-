import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.flags import load_flags
from app.core.prompt_builder import PromptBuilder
from app.core.session import CallSession
from app.core.voice_pipeline import VoicePipeline
from app.db import get_db
from app.models.call import Call
from app.models.tenant import Tenant
from app.services.llm.base import get_llm_provider
from app.services.stt.base import get_stt_provider
from app.services.tts.base import get_tts_provider
from app.utils.auth import hash_api_key
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["voice"])


async def _authenticate_ws(
    websocket: WebSocket,
    db: AsyncSession,
) -> Tenant | None:
    api_key = websocket.query_params.get("api_key", "")
    if not api_key:
        await websocket.close(code=4001, reason="Missing api_key query param")
        return None

    key_hash = hash_api_key(api_key)
    result = await db.execute(select(Tenant).where(Tenant.api_key_hash == key_hash))
    tenant = result.scalar_one_or_none()

    if not tenant:
        await websocket.close(code=4001, reason="Invalid API key")
        return None
    if tenant.status == "suspended":
        await websocket.close(code=4003, reason="Tenant suspended")
        return None
    return tenant


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> None:
    await websocket.accept()

    tenant = await _authenticate_ws(websocket, db)
    if not tenant:
        return

    # ── Optional campaign / contact context ──────────────────────────
    campaign_id_param = websocket.query_params.get("campaign_id")
    contact_id_param = websocket.query_params.get("contact_id")

    campaign = None
    contact = None

    if campaign_id_param:
        try:
            # Import here to avoid circular imports at module load time
            from app.models.campaign import Campaign  # type: ignore[attr-defined]

            res = await db.execute(
                select(Campaign).where(
                    Campaign.id == uuid.UUID(campaign_id_param),
                    Campaign.tenant_id == tenant.id,
                )
            )
            campaign = res.scalar_one_or_none()
            if campaign is None:
                log.warning("voice_campaign_not_found", campaign_id=campaign_id_param)
        except (ValueError, Exception) as exc:
            log.warning("voice_campaign_load_error", error=str(exc))

    if contact_id_param:
        try:
            from app.models.contact import Contact  # type: ignore[attr-defined]

            res = await db.execute(
                select(Contact).where(Contact.id == uuid.UUID(contact_id_param))
            )
            contact = res.scalar_one_or_none()
            if contact is None:
                log.warning("voice_contact_not_found", contact_id=contact_id_param)
        except (ValueError, Exception) as exc:
            log.warning("voice_contact_load_error", error=str(exc))

    # ── Assemble full system prompt from all layers ───────────────────
    persona_prompt = PromptBuilder().build(
        tenant=tenant,
        campaign=campaign,
        contact=contact,
    )

    # ── Feature flags ─────────────────────────────────────────────────
    flags = await load_flags(str(tenant.id), db)
    from app.config import get_settings
    _cfg = get_settings()
    stt_name = flags.get("FLAG_STT_PROVIDER", _cfg.stt_provider)
    tts_name = flags.get("FLAG_TTS_PROVIDER", _cfg.tts_provider)

    # ── Build CallSession ─────────────────────────────────────────────
    escalation_triggers: list[str] = []
    if campaign and campaign.escalation_triggers:
        triggers = campaign.escalation_triggers
        escalation_triggers = triggers if isinstance(triggers, list) else list(triggers)

    session = CallSession(
        tenant_id=str(tenant.id),
        persona_prompt=persona_prompt,
        campaign_id=campaign_id_param,
        contact_id=contact_id_param,
        escalation_triggers=escalation_triggers,
    )

    # ── Pre-populate opening line as first assistant turn ─────────────
    # The AI says the opening line the moment the call connects,
    # before the customer has spoken at all.
    if campaign and campaign.opening_line:
        opening = campaign.opening_line
        # Personalise with contact name if available
        if contact and contact.name:
            opening = opening.replace("[customer_name]", contact.name)
            opening = opening.replace("{customer_name}", contact.name)
        session.add_turn("assistant", opening)
        log.info("voice_opening_line_set", call_session=session.call_id)

    # ── Providers ─────────────────────────────────────────────────────
    stt = get_stt_provider(stt_name)
    tts = get_tts_provider(tts_name)
    llm = get_llm_provider()

    from app.core.rag import RAGEngine
    from app.services.vector_db.qdrant import QdrantVectorDB
    rag = RAGEngine(vector_db=QdrantVectorDB()) if flags.get("FLAG_RAG_ENABLED") else RAGEngine()

    pipeline = VoicePipeline(
        flags=flags,
        session=session,
        stt=stt,
        tts=tts,
        llm=llm,
        rag=rag,
    )

    # ── Create Call DB record ─────────────────────────────────────────
    call_kwargs: dict = {
        "tenant_id": tenant.id,
        "to_number": contact.phone_number if contact else "websocket",
        "status": "in_progress",
    }
    # Link campaign / contact if models have those FK columns
    try:
        if campaign_id_param:
            call_kwargs["campaign_id"] = uuid.UUID(campaign_id_param)
        if contact_id_param:
            call_kwargs["contact_id"] = uuid.UUID(contact_id_param)
    except (ValueError, Exception):
        pass

    call = Call(**call_kwargs)
    db.add(call)
    await db.flush()
    call_id = str(call.id)

    # ── Send opening audio if opening line was set ────────────────────
    if campaign and campaign.opening_line:
        try:
            opening_audio = await tts.synthesise(session.messages[0]["content"])
            await websocket.send_bytes(opening_audio)
        except Exception as exc:
            log.warning("voice_opening_audio_error", error=str(exc))

    await websocket.send_json({"event": "call.started", "call_id": call_id})
    log.info("ws_call_started", call_id=call_id, tenant_id=str(tenant.id),
             campaign_id=campaign_id_param, contact_id=contact_id_param)

    max_turns = flags.get("FLAG_LLM_MAX_TURNS", 30)

    try:
        while True:
            audio_data = await websocket.receive_bytes()

            if session.turn_count >= max_turns:
                await websocket.send_json(
                    {"event": "call.max_turns_reached", "call_id": call_id}
                )
                break

            response_audio = await pipeline.process_audio_chunk(audio_data)
            await websocket.send_bytes(response_audio)

    except WebSocketDisconnect:
        log.info("ws_call_disconnected", call_id=call_id)
    except Exception as e:
        log.error("ws_call_error", call_id=call_id, error=str(e))
        await websocket.send_json({"event": "error", "detail": str(e)})
    finally:
        call.status = "completed"
        call.transcript = session.get_transcript()
        call.duration_seconds = session.turn_count * 5
        db.add(call)
        await db.flush()

        # Fire post-call processing
        _trigger_post_call(
            call_id=call_id,
            transcript=call.transcript,
            tenant_id=str(tenant.id),
            campaign_id=campaign_id_param,
            contact_id=contact_id_param,
            escalation_detected=session.escalation_detected,
            escalation_trigger_phrase=session.escalation_trigger_phrase,
        )

        await websocket.close()
        log.info("ws_call_ended", call_id=call_id, turns=session.turn_count,
                 escalation=session.escalation_detected)


def _trigger_post_call(
    call_id: str,
    transcript: str,
    tenant_id: str,
    campaign_id: str | None,
    contact_id: str | None,
    escalation_detected: bool,
    escalation_trigger_phrase: str | None,
) -> None:
    """Fire Celery post-call task. Wrapped so failures don't crash the WebSocket finally block."""
    try:
        from workers.tasks.post_call import process_post_call
        process_post_call.delay(
            call_id=call_id,
            transcript=transcript,
            tenant_flags={},
            campaign_id=campaign_id,
            contact_id=contact_id,
            escalation_detected=escalation_detected,
            escalation_trigger_phrase=escalation_trigger_phrase,
        )
        log.info("post_call_queued", call_id=call_id)
    except Exception as exc:
        log.error("post_call_queue_error", call_id=call_id, error=str(exc))