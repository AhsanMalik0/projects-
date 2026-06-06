import time
import base64

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.stt.base import STTProvider
from app.utils.logging import get_logger

log = get_logger(__name__)


class GeminiSTT(STTProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        start = time.monotonic()

        # Encode audio as base64 and send inline to Gemini
        audio_b64 = base64.b64encode(audio).decode("utf-8")

        lang_hint = f" The audio language is {language}." if language else ""
        prompt = f"Transcribe the following audio exactly as spoken, outputting only the transcript text with no additional commentary.{lang_hint}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=audio, mime_type="audio/wav"),
                prompt,
            ],
        )

        transcript = response.text.strip() if response.text else ""

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "gemini_stt",
            latency_ms=round(elapsed_ms, 2),
            length=len(transcript),
        )
        return transcript
