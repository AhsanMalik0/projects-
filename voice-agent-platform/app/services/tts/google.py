import time

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.tts.base import TTSProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class OpenAITTS(TTSProvider):
    """TTS provider using OpenAI's TTS API."""

    def __init__(self, voice: str = "alloy") -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.voice = voice

    async def synthesise(self, text: str) -> bytes:
        start = time.monotonic()

        response = await self.client.audio.speech.create(
            model="tts-1",
            voice=self.voice,
            input=text,
        )

        audio_bytes = response.content

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "openai_tts",
            latency_ms=round(elapsed_ms, 2),
            text_len=len(text),
            audio_bytes=len(audio_bytes),
        )
        return audio_bytes


# Backward-compatible alias
GoogleTTS = OpenAITTS
