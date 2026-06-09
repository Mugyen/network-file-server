"""Tests for atomic JSON persistence utilities."""

import json
from pathlib import Path

import pytest

from server.app.services.persistence import read_json, write_json_atomic


@pytest.mark.asyncio
async def test_write_json_atomic_creates_file(tmp_path: Path) -> None:
    """write_json_atomic creates a file with correct JSON content."""
    target = tmp_path / "data.json"
    data = {"key": "value", "count": 42}
    await write_json_atomic(target, data)

    assert target.exists()
    content = json.loads(target.read_text())
    assert content == data


@pytest.mark.asyncio
async def test_write_json_atomic_no_temp_file_left(tmp_path: Path) -> None:
    """After write_json_atomic, no .tmp files remain (os.replace cleans up)."""
    target = tmp_path / "data.json"
    await write_json_atomic(target, {"a": 1})

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


@pytest.mark.asyncio
async def test_write_json_atomic_overwrites_existing(tmp_path: Path) -> None:
    """write_json_atomic overwrites existing file content."""
    target = tmp_path / "data.json"
    await write_json_atomic(target, {"old": True})
    await write_json_atomic(target, {"new": True})

    content = json.loads(target.read_text())
    assert content == {"new": True}


@pytest.mark.asyncio
async def test_read_json_nonexistent_returns_empty_dict(tmp_path: Path) -> None:
    """read_json returns empty dict for a file that does not exist."""
    result = await read_json(tmp_path / "missing.json")
    assert result == {}


@pytest.mark.asyncio
async def test_read_json_valid_file(tmp_path: Path) -> None:
    """read_json returns parsed dict for a valid JSON file."""
    target = tmp_path / "data.json"
    target.write_text(json.dumps({"hello": "world"}))
    result = await read_json(target)
    assert result == {"hello": "world"}


@pytest.mark.asyncio
async def test_read_json_malformed_raises_value_error(tmp_path: Path) -> None:
    """read_json raises ValueError on malformed JSON (strict contract)."""
    target = tmp_path / "bad.json"
    target.write_text("{not valid json")
    with pytest.raises(ValueError, match="Malformed JSON"):
        await read_json(target)
