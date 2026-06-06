import asyncio
import time
from functools import partial

from deepgram import DeepgramClient, PrerecordedOptions

from app.config import get_settings
from app.services.stt.base import STTProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class DeepgramSTT(STTProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = DeepgramClient(settings.deepgram_api_key)

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        start = time.monotonic()

        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            language=language or "en",
        )

        source = {"buffer": audio, "mimetype": "audio/wav"}
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            partial(self.client.listen.rest.v("1").transcribe_file, source, options),
        )

        transcript = (
            response.results.channels[0].alternatives[0].transcript
            if response.results.channels
            else ""
        )

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info("deepgram_transcription", latency_ms=round(elapsed_ms, 2), length=len(transcript))
        return transcript
