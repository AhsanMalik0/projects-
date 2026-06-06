from abc import ABC, abstractmethod


class TTSProvider(ABC):
    @abstractmethod
    async def synthesise(self, text: str) -> bytes:
        """Convert text to speech audio bytes."""


def get_tts_provider(provider_name: str) -> TTSProvider:
    if provider_name == "elevenlabs":
        from app.services.tts.elevenlabs import ElevenLabsTTS
        return ElevenLabsTTS()
    elif provider_name in ("google", "openai"):
        from app.services.tts.google import OpenAITTS
        return OpenAITTS()
    elif provider_name == "gemini":
        from app.services.tts.gemini import GeminiTTS
        return GeminiTTS()
    else:
        raise ValueError(f"Unknown TTS provider: {provider_name}")
