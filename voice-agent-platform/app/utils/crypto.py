import base64

from cryptography.fernet import Fernet

from app.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.secret_key.encode()
    padded = base64.urlsafe_b64encode(key.ljust(32, b"\0")[:32])
    return Fernet(padded)


def encrypt_text(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
