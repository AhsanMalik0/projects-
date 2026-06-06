import time

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.tts.base import TTSProvider
from app.utils.logging import get_logger

log = get_logger(__name__)

# Available Gemini TTS voices
# Aoede, Charon, Fenrir, Kore, Puck, Schedar, Umbriel, Achernar,
# Algieba, Alnilam, Alya, Autonoe, Callisto, Despina, Enceladus,
# Gacrux, Iocaste, Laomedeia, Leda, Rasalas, Sulafat, Vindemiatrix, Zubenelgenubi
GEMINI_DEFAULT_VOICE = "Kore"


class GeminiTTS(TTSProvider):
    """TTS provider using Gemini's native text-to-speech API."""

    def __init__(self, voice: str = GEMINI_DEFAULT_VOICE) -> None:
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.voice = voice
        self.model = "gemini-2.5-flash-preview-tts"

    async def synthesise(self, text: str) -> bytes:
        start = time.monotonic()

        response = self.client.models.generate_content(
            model=self.model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.voice,
                        )
                    )
                ),
            ),
        )

        # Extract raw PCM audio bytes from response
        audio_bytes = response.candidates[0].content.parts[0].inline_data.data

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "gemini_tts",
            latency_ms=round(elapsed_ms, 2),
            text_len=len(text),
            audio_bytes=len(audio_bytes),
            voice=self.voice,
        )
        return audio_bytes
