from abc import ABC, abstractmethod


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        """Transcribe audio bytes to text."""


def get_stt_provider(provider_name: str) -> STTProvider:
    if provider_name == "deepgram":
        from app.services.stt.deepgram import DeepgramSTT
        return DeepgramSTT()
    elif provider_name == "whisper":
        from app.services.stt.whisper import WhisperSTT
        return WhisperSTT()
    elif provider_name == "gemini":
        from app.services.stt.gemini import GeminiSTT
        return GeminiSTT()
    else:
        raise ValueError(f"Unknown STT provider: {provider_name}")
