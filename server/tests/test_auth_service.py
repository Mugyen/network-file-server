"""Tests for the auth service: password hashing, verification, and token management."""

from pathlib import Path

import bcrypt
import pytest

from server.app.config import ServerConfig, create_default_config
from server.app.main import create_app
from server.app.services.auth_service import (
    AuthTokenService,
    hash_password,
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


class TestTokenServiceAppWiring:
    """Tests for create_app wiring AuthTokenService onto app.state."""

    def test_app_without_password_has_no_token_service(self, tmp_path: Path) -> None:
        shared = tmp_path / "shared"
        shared.mkdir()
        app = create_app(create_default_config(shared_folder=shared, port=8000))
        assert app.state.token_service is None

    def test_app_with_password_gets_working_token_service(self, tmp_path: Path) -> None:
        shared = tmp_path / "shared"
        shared.mkdir()
        config = ServerConfig(
            shared_folder=shared,
            port=8000,
            password_hash=hash_password("test-password-123"),
            read_only=False,
            receive=False,
            mount_code=None,
            relay_url=None,
            identity_secret=None,
        )
        app = create_app(config)
        token_service = app.state.token_service
        assert isinstance(token_service, AuthTokenService)
        token = token_service.create_token()
        assert token_service.validate_token(token) is True

    def test_each_app_gets_independent_token_service(self, tmp_path: Path) -> None:
        """Tokens minted by one app instance are rejected by another (fresh secret)."""
        shared = tmp_path / "shared"
        shared.mkdir()
        config = ServerConfig(
            shared_folder=shared,
            port=8000,
            password_hash=hash_password("test-password-123"),
            read_only=False,
            receive=False,
            mount_code=None,
            relay_url=None,
            identity_secret=None,
        )
        app_a = create_app(config)
        app_b = create_app(config)
        token_a = app_a.state.token_service.create_token()
        assert app_b.state.token_service.validate_token(token_a) is False
