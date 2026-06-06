import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-32bytes-long!!!")
os.environ.setdefault("API_KEY_SALT", "test-salt-value")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
