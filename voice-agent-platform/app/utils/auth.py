import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> str:
    return f"vap_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    settings = get_settings()
    return hmac.HMAC(
        settings.api_key_salt.encode(),
        api_key.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_api_key(api_key), hashed)


def create_jwt_token(
    data: dict[str, str | int],
    expires_minutes: int = 15,
) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_jwt_token(token: str) -> dict[str, str | int]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def sign_webhook_payload(payload: bytes, secret: str) -> str:
    return hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_webhook_signature(payload: bytes, secret: str, signature: str) -> bool:
    expected = sign_webhook_payload(payload, secret)
    return hmac.compare_digest(expected, signature)
