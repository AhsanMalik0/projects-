import time

import anthropic

from app.config import get_settings
from app.services.llm.base import LLMProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class AnthropicLLM(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        start = time.monotonic()

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        msg = await self.client.messages.create(**kwargs)
        response_text = msg.content[0].text

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "anthropic_llm",
            latency_ms=round(elapsed_ms, 2),
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )
        return response_text
