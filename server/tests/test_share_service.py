"""Unit tests for ShareLinkService, ShareTTL enum, and share schemas."""

import time

import pytest
from itsdangerous import BadSignature

from server.app.models.enums import ShareTTL
from server.app.models.schemas import CreateShareRequest, ShareLinkInfo
from server.app.services.share_service import (
    ShareLinkExpiredError,
    ShareLinkNotFoundError,
    ShareLinkRecord,
    ShareLinkRevokedError,
    ShareLinkService,
    get_share_service,
    set_share_service,
)


# --- ShareTTL enum tests ---


class TestShareTTL:
    def test_has_exactly_four_members(self) -> None:
        assert len(ShareTTL) == 4

    def test_fifteen_minutes(self) -> None:
        assert ShareTTL.FIFTEEN_MINUTES == 900

    def test_one_hour(self) -> None:
        assert ShareTTL.ONE_HOUR == 3600

    def test_six_hours(self) -> None:
        assert ShareTTL.SIX_HOURS == 21600

    def test_twenty_four_hours(self) -> None:
        assert ShareTTL.TWENTY_FOUR_HOURS == 86400

    def test_is_int_enum(self) -> None:
        assert isinstance(ShareTTL.ONE_HOUR, int)


# --- ShareLinkService tests ---


class TestShareLinkServiceCreate:
    def test_create_link_returns_nonempty_token(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_link_registers_in_active_links(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        active = service.list_active_links()
        assert len(active) == 1
        assert active[0].token == token

    def test_create_link_different_files_different_tokens(self) -> None:
        service = ShareLinkService("test-secret-key")
        t1 = service.create_link("file1.txt", ShareTTL.ONE_HOUR)
        t2 = service.create_link("file2.txt", ShareTTL.ONE_HOUR)
        assert t1 != t2


class TestShareLinkServiceValidate:
    def test_validate_valid_token_returns_file_path(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        result = service.validate_token(token)
        assert result == "docs/readme.txt"

    def test_validate_revoked_token_raises_revoked_error(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        service.revoke_link(token)
        with pytest.raises(ShareLinkRevokedError):
            service.validate_token(token)

    def test_validate_expired_token_raises_expired_error(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.FIFTEEN_MINUTES)
        # Directly set the TTL to 1 second for this record to force expiry
        record = service._active_links[token]
        service._active_links[token] = ShareLinkRecord(
            token=record.token,
            file_path=record.file_path,
            created_at=record.created_at,
            ttl_seconds=1,
        )
        time.sleep(2)
        with pytest.raises(ShareLinkExpiredError):
            service.validate_token(token)

    def test_validate_tampered_token_raises_bad_signature(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        tampered = token + "tampered"
        # Token is tampered but still in _active_links -- add fake entry
        service._active_links[tampered] = service._active_links[token]
        with pytest.raises(BadSignature):
            service.validate_token(tampered)


class TestShareLinkServiceRevoke:
    def test_revoke_link_removes_from_active(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        service.revoke_link(token)
        assert len(service.list_active_links()) == 0

    def test_revoke_unknown_token_raises_not_found(self) -> None:
        service = ShareLinkService("test-secret-key")
        with pytest.raises(ShareLinkNotFoundError):
            service.revoke_link("nonexistent-token")


class TestShareLinkServiceListActive:
    def test_list_active_links_returns_non_expired(self) -> None:
        service = ShareLinkService("test-secret-key")
        service.create_link("file1.txt", ShareTTL.ONE_HOUR)
        service.create_link("file2.txt", ShareTTL.SIX_HOURS)
        active = service.list_active_links()
        assert len(active) == 2

    def test_list_active_links_filters_expired(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = service.create_link("file1.txt", ShareTTL.FIFTEEN_MINUTES)
        service.create_link("file2.txt", ShareTTL.ONE_HOUR)
        # Force first token to be expired
        record = service._active_links[token]
        service._active_links[token] = ShareLinkRecord(
            token=record.token,
            file_path=record.file_path,
            created_at=record.created_at,
            ttl_seconds=1,
        )
        time.sleep(2)
        active = service.list_active_links()
        assert len(active) == 1
        assert active[0].file_path == "file2.txt"


# --- Singleton access tests ---


class TestShareServiceSingleton:
    def test_get_share_service_raises_when_not_initialized(self) -> None:
        # Reset module state
        import server.app.services.share_service as mod
        mod._share_service = None
        with pytest.raises(RuntimeError):
            get_share_service()

    def test_set_then_get_returns_service(self) -> None:
        service = ShareLinkService("test-secret-key")
        set_share_service(service)
        result = get_share_service()
        assert result is service


# --- ShareLinkRecord dataclass tests ---


class TestShareLinkRecord:
    def test_record_has_expected_fields(self) -> None:
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        record = ShareLinkRecord(
            token="abc",
            file_path="test.txt",
            created_at=now,
            ttl_seconds=3600,
        )
        assert record.token == "abc"
        assert record.file_path == "test.txt"
        assert record.created_at == now
        assert record.ttl_seconds == 3600


# --- Pydantic schema tests ---


class TestShareSchemas:
    def test_create_share_request_valid(self) -> None:
        req = CreateShareRequest(file_path="docs/readme.txt", ttl=ShareTTL.ONE_HOUR)
        assert req.file_path == "docs/readme.txt"
        assert req.ttl == ShareTTL.ONE_HOUR

    def test_share_link_info_valid(self) -> None:
        info = ShareLinkInfo(
            token="abc123",
            file_path="docs/readme.txt",
            file_name="readme.txt",
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T01:00:00Z",
            ttl_seconds=3600,
            share_url="http://localhost:8000/share/abc123",
        )
        assert info.token == "abc123"
        assert info.file_name == "readme.txt"
