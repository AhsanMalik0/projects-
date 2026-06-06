import time

from elevenlabs.client import ElevenLabs

from app.config import get_settings
from app.services.tts.base import TTSProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class ElevenLabsTTS(TTSProvider):
    def __init__(self, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> None:
        settings = get_settings()
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        self.voice_id = voice_id

    async def synthesise(self, text: str) -> bytes:
        start = time.monotonic()

        audio_iter = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        audio_bytes = b"".join(chunk for chunk in audio_iter)

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "elevenlabs_tts",
            latency_ms=round(elapsed_ms, 2),
            text_len=len(text),
            audio_bytes=len(audio_bytes),
        )
        return audio_bytes
