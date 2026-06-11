"""Unit tests for ShareLinkService, ShareTTL enum, and share schemas."""

import pytest
from itsdangerous import BadSignature

from server.app.config import create_default_config
from server.app.main import create_app
from server.app.models.enums import ShareTTL
from server.app.models.schemas import CreateShareRequest, ShareLinkInfo
from server.app.services.share_service import (
    ShareLinkExpiredError,
    ShareLinkNotFoundError,
    ShareLinkRecord,
    ShareLinkRevokedError,
    ShareLinkService,
)
from server.app.services.sqlite_store import ShareLinkRow, open_state_store
from server.tests.conftest import AdvanceableClock


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
    async def test_create_link_returns_record_with_nonempty_token(self) -> None:
        service = ShareLinkService("test-secret-key")
        record = await service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        assert isinstance(record, ShareLinkRecord)
        assert isinstance(record.token, str)
        assert len(record.token) > 0
        assert record.file_path == "docs/readme.txt"
        assert record.ttl_seconds == int(ShareTTL.ONE_HOUR)

    async def test_create_link_registers_in_active_links(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = (await service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)).token
        active = await service.list_active_links()
        assert len(active) == 1
        assert active[0].token == token

    async def test_create_link_different_files_different_tokens(self) -> None:
        service = ShareLinkService("test-secret-key")
        t1 = (await service.create_link("file1.txt", ShareTTL.ONE_HOUR)).token
        t2 = (await service.create_link("file2.txt", ShareTTL.ONE_HOUR)).token
        assert t1 != t2


class TestShareLinkServiceValidate:
    async def test_validate_valid_token_returns_file_path(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = (await service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)).token
        result = await service.validate_token(token)
        assert result == "docs/readme.txt"

    async def test_validate_revoked_token_raises_revoked_error(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = (await service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)).token
        await service.revoke_link(token)
        with pytest.raises(ShareLinkRevokedError):
            await service.validate_token(token)

    async def test_validate_expired_token_raises_expired_error(self) -> None:
        # Drive expiry through the public clock seam instead of mutating
        # the service's internal registry.
        clock = AdvanceableClock()
        service = ShareLinkService("test-secret-key", now_fn=clock)
        token = (await service.create_link("docs/readme.txt", ShareTTL.FIFTEEN_MINUTES)).token
        clock.advance(int(ShareTTL.FIFTEEN_MINUTES) + 1)
        with pytest.raises(ShareLinkExpiredError):
            await service.validate_token(token)

    async def test_validate_tampered_token_raises_bad_signature(self, tmp_path) -> None:
        # Seed a tampered token into the registry through the public
        # persistence path (sqlite store row loaded at construction), so
        # validation reaches the signature check and fails there.
        data_dir = tmp_path / "wfs_data"
        seed_service = ShareLinkService("test-secret-key", open_state_store(data_dir))
        record = await seed_service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)
        tampered = record.token + "tampered"
        open_state_store(data_dir).upsert_share_link(
            ShareLinkRow(
                token=tampered,
                file_path=record.file_path,
                created_at=record.created_at.isoformat(),
                ttl_seconds=record.ttl_seconds,
            )
        )
        service = ShareLinkService("test-secret-key", open_state_store(data_dir))
        with pytest.raises(BadSignature):
            await service.validate_token(tampered)


class TestShareLinkServiceRevoke:
    async def test_revoke_link_removes_from_active(self) -> None:
        service = ShareLinkService("test-secret-key")
        token = (await service.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)).token
        await service.revoke_link(token)
        assert len(await service.list_active_links()) == 0

    async def test_revoke_unknown_token_raises_not_found(self) -> None:
        service = ShareLinkService("test-secret-key")
        with pytest.raises(ShareLinkNotFoundError):
            await service.revoke_link("nonexistent-token")


class TestShareLinkServiceListActive:
    async def test_list_active_links_returns_non_expired(self) -> None:
        service = ShareLinkService("test-secret-key")
        await service.create_link("file1.txt", ShareTTL.ONE_HOUR)
        await service.create_link("file2.txt", ShareTTL.SIX_HOURS)
        active = await service.list_active_links()
        assert len(active) == 2

    async def test_list_active_links_filters_expired(self) -> None:
        # Advance the injected clock past the first link's TTL but within
        # the second's, so only the expired one is filtered out.
        clock = AdvanceableClock()
        service = ShareLinkService("test-secret-key", now_fn=clock)
        await service.create_link("file1.txt", ShareTTL.FIFTEEN_MINUTES)
        await service.create_link("file2.txt", ShareTTL.ONE_HOUR)
        clock.advance(int(ShareTTL.FIFTEEN_MINUTES) + 1)
        active = await service.list_active_links()
        assert len(active) == 1
        assert active[0].file_path == "file2.txt"


# --- App wiring tests (replaces the removed module-level singleton) ---


class TestShareServiceAppWiring:
    def test_create_app_attaches_share_service(self, tmp_path) -> None:
        shared = tmp_path / "shared"
        shared.mkdir()
        app = create_app(create_default_config(shared_folder=shared, port=8000))
        assert isinstance(app.state.share_service, ShareLinkService)

    async def test_share_secret_persists_across_app_instances(self, tmp_path) -> None:
        """Tokens survive an app rebuild: the secret lives in the sqlite state store."""
        shared = tmp_path / "shared"
        shared.mkdir()
        app1 = create_app(create_default_config(shared_folder=shared, port=8000))
        token = (
            await app1.state.share_service.create_link(
                "docs/readme.txt", ShareTTL.ONE_HOUR
            )
        ).token

        app2 = create_app(create_default_config(shared_folder=shared, port=8000))
        assert (await app2.state.share_service.validate_token(token)) == "docs/readme.txt"


class TestShareLinkPersistence:
    async def test_share_links_survive_reinstantiation(self, tmp_path) -> None:
        data_dir = tmp_path / "wfs_data"
        service1 = ShareLinkService("test-secret-key", open_state_store(data_dir))
        token = (await service1.create_link("docs/readme.txt", ShareTTL.ONE_HOUR)).token

        service2 = ShareLinkService("test-secret-key", open_state_store(data_dir))
        active = await service2.list_active_links()
        assert len(active) == 1
        assert active[0].token == token
        assert (await service2.validate_token(token)) == "docs/readme.txt"


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
