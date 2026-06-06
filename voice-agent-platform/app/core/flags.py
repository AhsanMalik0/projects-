from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import TenantFlag

DEFAULTS: dict[str, Any] = {
    "FLAG_RAG_ENABLED": False,
    "FLAG_RAG_MAX_CHUNKS": 5,
    "FLAG_RAG_RERANKER": False,
    "FLAG_RAG_KEYWORD_FALLBACK": False,
    "FLAG_NLU_ENTITY_EXTRACTION": True,
    "FLAG_NLU_SENTIMENT_REALTIME": False,
    "FLAG_NLU_CONFIDENCE_THRESHOLD": 0.75,
    "FLAG_NLU_CUSTOM_ENTITIES": False,
    "FLAG_STT_PROVIDER": "deepgram",
    "FLAG_TTS_PROVIDER": "elevenlabs",
    "FLAG_LLM_GUARDRAILS": True,
    "FLAG_LLM_MAX_TURNS": 30,
    "FLAG_POSTCALL_SUMMARY_ENABLED": True,
    "FLAG_POSTCALL_KEYPOINTS_EXTRACT": True,
    "FLAG_POSTCALL_ACTION_ITEMS": False,
    "FLAG_POSTCALL_SENTIMENT_REPORT": False,
    "FLAG_POSTCALL_ESCALATION_DETECT": False,
    "FLAG_POSTCALL_NER_SUMMARY": False,
    "FLAG_OUTPUT_WEBHOOK_POSTCALL": True,
    "FLAG_OUTPUT_WEBHOOK_RETRY": True,
    "FLAG_CONTROL_TENANT_SELF_SERVE": True,
    "FLAG_DATA_TRANSCRIPT_ENCRYPTION": False,
    "FLAG_DATA_GDPR_REDACTION": False,
    "FLAG_DATA_KB_FILE_TYPES": ["pdf", "docx", "txt"],
}


class FlagResolver:
    def __init__(self, tenant_id: str, overrides: dict[str, Any]) -> None:
        self._overrides = overrides
        self.tenant_id = tenant_id

    def get(self, flag: str, default: Any = None) -> Any:
        if flag in self._overrides:
            return self._overrides[flag]
        return DEFAULTS.get(flag, default)

    def enabled(self, flag: str) -> bool:
        return bool(self.get(flag, False))


async def load_flags(tenant_id: str, db: AsyncSession) -> FlagResolver:
    rows = await TenantFlag.get_all(tenant_id, db)
    overrides = {r.flag_key: r.flag_value for r in rows}
    return FlagResolver(tenant_id, overrides)
