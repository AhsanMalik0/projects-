from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.flags import load_flags
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

    flags = await load_flags(str(tenant.id), db)

    from app.config import get_settings
    _cfg = get_settings()
    stt_name = flags.get("FLAG_STT_PROVIDER", _cfg.stt_provider)
    tts_name = flags.get("FLAG_TTS_PROVIDER", _cfg.tts_provider)

    session = CallSession(
        tenant_id=str(tenant.id),
        persona_prompt=tenant.persona_prompt or "You are a helpful AI voice assistant.",
    )

    stt = get_stt_provider(stt_name)
    tts = get_tts_provider(tts_name)
    llm = get_llm_provider()

    pipeline = VoicePipeline(
        flags=flags,
        session=session,
        stt=stt,
        tts=tts,
        llm=llm,
    )

    call = Call(
        tenant_id=tenant.id,
        to_number="websocket",
        status="in_progress",
    )
    db.add(call)
    await db.flush()
    call_id = str(call.id)

    await websocket.send_json({"event": "call.started", "call_id": call_id})
    log.info("ws_call_started", call_id=call_id, tenant_id=str(tenant.id))

    max_turns = flags.get("FLAG_LLM_MAX_TURNS", 30)

    try:
        while True:
            audio_data = await websocket.receive_bytes()

            if session.turn_count >= max_turns:
                await websocket.send_json(
                    {
                        "event": "call.max_turns_reached",
                        "call_id": call_id,
                    }
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

        await websocket.close()
        log.info("ws_call_ended", call_id=call_id, turns=session.turn_count)
