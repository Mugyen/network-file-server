"""Tests for the auth service: password hashing, verification, and token management."""

import bcrypt
import pytest

from server.app.services.auth_service import (
    AuthTokenService,
    get_token_service,
    hash_password,
    set_token_service,
    verify_password,
)


class TestHashPassword:
    """Tests for hash_password function."""

    def test_returns_bytes(self) -> None:
        result = hash_password("secret")
        assert isinstance(result, bytes)

    def test_result_verifiable_with_bcrypt(self) -> None:
        hashed = hash_password("secret")
        assert bcrypt.checkpw(b"secret", hashed)

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            hash_password("")

    def test_rejects_over_72_bytes(self) -> None:
        long_password = "a" * 73
        with pytest.raises(ValueError, match="72"):
            hash_password(long_password)

    def test_accepts_exactly_72_bytes(self) -> None:
        password_72 = "a" * 72
        hashed = hash_password(password_72)
        assert bcrypt.checkpw(password_72.encode("utf-8"), hashed)


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_correct_password_returns_true(self) -> None:
        hashed = hash_password("secret")
        assert verify_password("secret", hashed) is True

    def test_wrong_password_returns_false(self) -> None:
        hashed = hash_password("secret")
        assert verify_password("wrong", hashed) is False

    def test_empty_string_raises_value_error(self) -> None:
        hashed = hash_password("secret")
        with pytest.raises(ValueError, match="empty"):
            verify_password("", hashed)


class TestAuthTokenService:
    """Tests for AuthTokenService token creation and validation."""

    def test_create_token_returns_non_empty_string(self) -> None:
        service = AuthTokenService("test-secret-key-1234567890")
        token = service.create_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_validate_token_accepts_valid_token(self) -> None:
        service = AuthTokenService("test-secret-key-1234567890")
        token = service.create_token()
        assert service.validate_token(token) is True

    def test_validate_token_rejects_garbage(self) -> None:
        service = AuthTokenService("test-secret-key-1234567890")
        assert service.validate_token("garbage") is False

    def test_validate_token_rejects_empty_string(self) -> None:
        service = AuthTokenService("test-secret-key-1234567890")
        assert service.validate_token("") is False

    def test_different_secrets_reject_each_others_tokens(self) -> None:
        service_a = AuthTokenService("secret-a-1234567890")
        service_b = AuthTokenService("secret-b-9876543210")
        token_a = service_a.create_token()
        token_b = service_b.create_token()
        assert service_a.validate_token(token_b) is False
        assert service_b.validate_token(token_a) is False


class TestTokenServiceGlobalAccess:
    """Tests for module-level get/set token service functions."""

    def test_get_before_set_raises_runtime_error(self) -> None:
        # Reset the module state
        set_token_service.__module__  # ensure import
        import server.app.services.auth_service as mod

        original = mod._token_service
        mod._token_service = None
        try:
            with pytest.raises(RuntimeError):
                get_token_service()
        finally:
            mod._token_service = original

    def test_set_then_get_returns_same_instance(self) -> None:
        service = AuthTokenService("test-key-for-global")
        set_token_service(service)
        assert get_token_service() is service
