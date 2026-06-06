import io
import time

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.stt.base import STTProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class WhisperSTT(STTProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        start = time.monotonic()

        audio_file = io.BytesIO(audio)
        audio_file.name = "audio.wav"

        kwargs: dict = {"model": "whisper-1", "file": audio_file}
        if language:
            kwargs["language"] = language

        response = await self.client.audio.transcriptions.create(**kwargs)
        transcript = response.text

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info("whisper_transcription", latency_ms=round(elapsed_ms, 2), length=len(transcript))
        return transcript
