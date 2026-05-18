"""Password hashing/verification: happy, edge, failure."""

import pytest

from accounts import WeakPasswordError, hash_password, verify_password


def test_hash_and_verify_roundtrip():
    h = hash_password("correct horse")
    assert isinstance(h, bytes)
    assert verify_password("correct horse", h) is True


def test_verify_wrong_password_returns_false():
    h = hash_password("s3cret")
    assert verify_password("wrong", h) is False


def test_hash_distinct_salts():
    assert hash_password("samepw") != hash_password("samepw")


def test_empty_password_rejected():
    with pytest.raises(WeakPasswordError):
        hash_password("")
    with pytest.raises(WeakPasswordError):
        verify_password("", hash_password("x"))


def test_password_over_72_bytes_rejected():
    with pytest.raises(WeakPasswordError):
        hash_password("a" * 73)


def test_multibyte_password_byte_limit():
    # 'é' is 2 UTF-8 bytes; 37 of them = 74 bytes > 72.
    with pytest.raises(WeakPasswordError):
        hash_password("é" * 37)


def test_empty_hash_rejected():
    with pytest.raises(ValueError):
        verify_password("x", b"")
