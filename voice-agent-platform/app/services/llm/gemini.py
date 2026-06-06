import time

from google import genai

from app.config import get_settings
from app.services.llm.base import LLMProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class GeminiLLM(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.llm_model or "gemini-2.0-flash"

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        start = time.monotonic()

        contents: list[dict[str, str]] = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        config: dict = {"max_output_tokens": max_tokens}
        if system_prompt:
            config["system_instruction"] = system_prompt

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        response_text = response.text or ""

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "gemini_llm",
            latency_ms=round(elapsed_ms, 2),
            model=self.model,
        )
        return response_text
