"""Tests for shared.identity_sig — HMAC identity signing/verification."""

import pytest

from shared.identity_sig import sign_identity, verify_identity


def test_sign_verify_round_trip() -> None:
    sig = sign_identity("secret", "alice", "write", True)
    assert verify_identity("secret", "alice", "write", True, sig) is True


def test_wrong_secret_fails() -> None:
    sig = sign_identity("secret-a", "alice", "write", True)
    assert verify_identity("secret-b", "alice", "write", True, sig) is False


def test_tampered_user_fails() -> None:
    sig = sign_identity("secret", "alice", "write", True)
    assert verify_identity("secret", "mallory", "write", True, sig) is False


def test_tampered_role_fails() -> None:
    sig = sign_identity("secret", "alice", "read", True)
    assert verify_identity("secret", "alice", "write", True, sig) is False


def test_tampered_bypass_fails() -> None:
    sig = sign_identity("secret", "alice", "write", True)
    assert verify_identity("secret", "alice", "write", False, sig) is False


def test_empty_signature_returns_false() -> None:
    assert verify_identity("secret", "alice", "write", True, "") is False


def test_signature_is_deterministic() -> None:
    a = sign_identity("secret", "alice", "write", True)
    b = sign_identity("secret", "alice", "write", True)
    assert a == b


def test_sign_rejects_empty_secret() -> None:
    with pytest.raises(ValueError):
        sign_identity("", "alice", "write", True)


def test_verify_rejects_empty_secret() -> None:
    with pytest.raises(ValueError):
        verify_identity("", "alice", "write", True, "sig")
