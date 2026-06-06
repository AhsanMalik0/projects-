from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Core
    app_env: str = "development"
    secret_key: str = "change-me"
    api_key_salt: str = "change-me"

    # DB
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/voiceagent"
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_provider: str = "anthropic"

    # STT / TTS
    stt_provider: str = "gemini"
    tts_provider: str = "gemini"
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""

    # Vector DB
    pinecone_api_key: str = ""
    pinecone_index_name: str = "voice-agent-kb"
    pinecone_environment: str = "us-east-1-aws"

    # Observability
    sentry_dsn: str = ""

    # CORS
    cors_origins: list[str] = ["*"]

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Upload limits
    max_upload_size_mb: int = 20

    # Telephony
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
