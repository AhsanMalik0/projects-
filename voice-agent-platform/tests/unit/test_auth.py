from app.utils.auth import (
    create_jwt_token,
    decode_jwt_token,
    generate_api_key,
    hash_api_key,
    sign_webhook_payload,
    verify_api_key,
    verify_webhook_signature,
)


class TestAPIKeyGeneration:
    def test_generate_api_key_format(self) -> None:
        key = generate_api_key()
        assert key.startswith("vap_")
        assert len(key) > 10

    def test_generate_unique_keys(self) -> None:
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_hash_api_key_deterministic(self) -> None:
        key = "vap_test_key_123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2

    def test_verify_api_key_correct(self) -> None:
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert verify_api_key(key, hashed) is True

    def test_verify_api_key_wrong(self) -> None:
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert verify_api_key("wrong_key", hashed) is False


class TestJWT:
    def test_create_and_decode_token(self) -> None:
        data = {"sub": "tenant_123", "role": "admin"}
        token = create_jwt_token(data)
        decoded = decode_jwt_token(token)
        assert decoded["sub"] == "tenant_123"
        assert decoded["role"] == "admin"
        assert "exp" in decoded


class TestWebhookSignature:
    def test_sign_and_verify(self) -> None:
        payload = b'{"event": "call.completed"}'
        secret = "webhook_secret_123"
        signature = sign_webhook_payload(payload, secret)
        assert verify_webhook_signature(payload, secret, signature) is True

    def test_verify_wrong_signature(self) -> None:
        payload = b'{"event": "call.completed"}'
        secret = "webhook_secret_123"
        assert verify_webhook_signature(payload, secret, "wrong_sig") is False

    def test_verify_tampered_payload(self) -> None:
        payload = b'{"event": "call.completed"}'
        secret = "webhook_secret_123"
        signature = sign_webhook_payload(payload, secret)
        tampered = b'{"event": "call.hacked"}'
        assert verify_webhook_signature(tampered, secret, signature) is False
