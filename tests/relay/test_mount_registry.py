"""Tests for MountRegistry service — register, deregister, get_connection lifecycle."""

import time

import pytest

from relay.app.enums import MountStatus
from relay.app.exceptions import MountExpiredError, MountNotFoundError, MountOfflineError
from relay.app.services.mount_registry import (
    MountRegistry,
    generate_mount_code,
    get_registry,
    set_registry,
)
from tests.relay.conftest import MockTunnelConnection


def _now() -> float:
    """Return current monotonic time for test convenience."""
    return time.monotonic()


# ---------------------------------------------------------------------------
# generate_mount_code
# ---------------------------------------------------------------------------


def test_generate_mount_code_returns_8_char_string() -> None:
    code = generate_mount_code()
    assert isinstance(code, str)
    assert len(code) == 8


def test_generate_mount_code_returns_unique_values() -> None:
    codes = {generate_mount_code() for _ in range(20)}
    assert len(codes) == 20


# ---------------------------------------------------------------------------
# get_registry / set_registry
# ---------------------------------------------------------------------------


def test_get_registry_raises_if_not_set() -> None:
    set_registry(None)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="MountRegistry has not been initialized"):
        get_registry()


def test_set_registry_and_get_registry_round_trip() -> None:
    reg = MountRegistry()
    set_registry(reg)
    assert get_registry() is reg


# ---------------------------------------------------------------------------
# MountStatus enum
# ---------------------------------------------------------------------------


def test_mount_status_values() -> None:
    assert MountStatus.ONLINE == "online"
    assert MountStatus.OFFLINE == "offline"
    assert MountStatus.EXPIRED == "expired"


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def test_register_stores_mount() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("ABCD1234", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    assert registry.has_mount("ABCD1234")


def test_register_empty_code_raises_value_error() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    with pytest.raises(ValueError, match="Mount code must not be empty"):
        registry.register("", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)


def test_register_overwrites_existing_mount() -> None:
    registry = MountRegistry()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    registry.register("CODE1234", conn1, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry.register("CODE1234", conn2, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    retrieved = registry.get_connection("CODE1234")
    assert retrieved is conn2


def test_register_stores_agent_ip_and_timestamps() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    now = _now()
    registry.register("IPTEST01", conn, agent_ip="10.0.0.5", created_at=now, expires_at=now + 3600)
    record = registry._mounts["IPTEST01"]
    assert record.agent_ip == "10.0.0.5"
    assert record.created_at == now
    assert record.expires_at == now + 3600


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------


def test_get_connection_returns_registered_connection() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("MYCODE12", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    retrieved = registry.get_connection("MYCODE12")
    assert retrieved is conn


def test_get_connection_unknown_code_raises_not_found() -> None:
    registry = MountRegistry()
    with pytest.raises(MountNotFoundError) as exc_info:
        registry.get_connection("UNKNOWN1")
    assert exc_info.value.code == "UNKNOWN1"


def test_get_connection_offline_mount_raises_offline_error() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("OFFLINE1", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry.mark_offline("OFFLINE1")
    with pytest.raises(MountOfflineError) as exc_info:
        registry.get_connection("OFFLINE1")
    assert exc_info.value.code == "OFFLINE1"


def test_get_connection_expired_mount_raises_expired_error() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("EXPIRED1", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry._mounts["EXPIRED1"].status = MountStatus.EXPIRED
    with pytest.raises(MountExpiredError) as exc_info:
        registry.get_connection("EXPIRED1")
    assert exc_info.value.code == "EXPIRED1"


# ---------------------------------------------------------------------------
# deregister
# ---------------------------------------------------------------------------


def test_deregister_removes_mount() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("DEREG123", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry.deregister("DEREG123")
    assert not registry.has_mount("DEREG123")


def test_deregister_then_get_connection_raises_not_found() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("DEREG456", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry.deregister("DEREG456")
    with pytest.raises(MountNotFoundError):
        registry.get_connection("DEREG456")


def test_deregister_unknown_code_raises_not_found() -> None:
    registry = MountRegistry()
    with pytest.raises(MountNotFoundError) as exc_info:
        registry.deregister("NOTHERE1")
    assert exc_info.value.code == "NOTHERE1"


# ---------------------------------------------------------------------------
# mark_offline
# ---------------------------------------------------------------------------


def test_mark_offline_changes_status() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("MARK0001", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry.mark_offline("MARK0001")
    record = registry._mounts["MARK0001"]
    assert record.status == MountStatus.OFFLINE


def test_mark_offline_unknown_code_raises_not_found() -> None:
    registry = MountRegistry()
    with pytest.raises(MountNotFoundError):
        registry.mark_offline("UNKNOWN2")


# ---------------------------------------------------------------------------
# has_mount
# ---------------------------------------------------------------------------


def test_has_mount_false_for_unknown_code() -> None:
    registry = MountRegistry()
    assert not registry.has_mount("NOTHERE2")


def test_has_mount_true_for_registered() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("PRESENT1", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    assert registry.has_mount("PRESENT1")


def test_has_mount_false_after_deregister() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("GONE0001", conn, agent_ip="127.0.0.1", created_at=_now(), expires_at=None)
    registry.deregister("GONE0001")
    assert not registry.has_mount("GONE0001")


# ---------------------------------------------------------------------------
# count_mounts_by_ip
# ---------------------------------------------------------------------------


def test_count_mounts_by_ip_returns_correct_count() -> None:
    registry = MountRegistry()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    registry.register("IP_A_001", conn1, agent_ip="10.0.0.1", created_at=_now(), expires_at=None)
    registry.register("IP_A_002", conn2, agent_ip="10.0.0.1", created_at=_now(), expires_at=None)
    assert registry.count_mounts_by_ip("10.0.0.1") == 2


def test_count_mounts_by_ip_returns_zero_for_unknown_ip() -> None:
    registry = MountRegistry()
    assert registry.count_mounts_by_ip("192.168.1.1") == 0


def test_count_mounts_by_ip_excludes_expired() -> None:
    registry = MountRegistry()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    registry.register("EXP_0001", conn1, agent_ip="10.0.0.2", created_at=_now(), expires_at=None)
    registry.register("EXP_0002", conn2, agent_ip="10.0.0.2", created_at=_now(), expires_at=None)
    # Mark one as expired
    registry._mounts["EXP_0001"].status = MountStatus.EXPIRED
    assert registry.count_mounts_by_ip("10.0.0.2") == 1


# ---------------------------------------------------------------------------
# active_mounts
# ---------------------------------------------------------------------------


def test_active_mounts_returns_non_expired() -> None:
    registry = MountRegistry()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    conn3 = MockTunnelConnection()
    registry.register("ACT_0001", conn1, agent_ip="10.0.0.1", created_at=_now(), expires_at=None)
    registry.register("ACT_0002", conn2, agent_ip="10.0.0.1", created_at=_now(), expires_at=None)
    registry.register("ACT_0003", conn3, agent_ip="10.0.0.1", created_at=_now(), expires_at=None)
    registry._mounts["ACT_0002"].status = MountStatus.EXPIRED
    active = registry.active_mounts()
    codes = {m.code for m in active}
    assert codes == {"ACT_0001", "ACT_0003"}


def test_active_mounts_returns_list_copy() -> None:
    registry = MountRegistry()
    conn = MockTunnelConnection()
    registry.register("COPY0001", conn, agent_ip="10.0.0.1", created_at=_now(), expires_at=None)
    active1 = registry.active_mounts()
    active2 = registry.active_mounts()
    assert active1 is not active2
