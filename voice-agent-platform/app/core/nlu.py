import json
from dataclasses import dataclass, field

from app.config import get_settings
from app.utils.logging import get_logger

log = get_logger(__name__)

EXTRACTION_PROMPT = (
    "Extract the intent and named entities from the following user utterance.\n"
    "Return ONLY a JSON object with these keys:\n"
    '- intent: string (e.g. "order_status", "refund_request", "booking", '
    '"greeting", "unclear")\n'
    "- confidence: float between 0.0 and 1.0\n"
    "- entities: object mapping entity type to value. Entity types: "
    "person_name, account_id, order_id, date, amount, phone, "
    "email{custom_types}\n\n"
    'User utterance: "{text}"\n\n'
    "Respond with ONLY the JSON object, no preamble or explanation."
)


@dataclass
class NLUResult:
    intent: str
    confidence: float
    entities: dict[str, str] = field(default_factory=dict)


class NLUProcessor:
    def __init__(self, custom_entity_types: list[str] | None = None) -> None:
        self.custom_entity_types = custom_entity_types or []

    async def process(self, text: str) -> NLUResult:
        settings = get_settings()

        custom_types_str = ""
        if self.custom_entity_types:
            custom_types_str = ", " + ", ".join(self.custom_entity_types)

        prompt = EXTRACTION_PROMPT.format(text=text, custom_types=custom_types_str)

        from app.services.llm.base import get_llm_provider

        llm = get_llm_provider(settings.llm_provider)
        raw_text = await llm.generate(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        raw_text = raw_text.strip()
        log.info("nlu_raw_response", text=raw_text[:200])

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            log.warning("nlu_parse_error", raw=raw_text[:200])
            return NLUResult(intent="unclear", confidence=0.0)

        return NLUResult(
            intent=data.get("intent", "unclear"),
            confidence=float(data.get("confidence", 0.0)),
            entities=data.get("entities", {}),
        )
