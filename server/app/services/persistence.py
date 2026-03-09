"""Atomic JSON read/write utility for persistent storage."""

import json
import os
import tempfile
from pathlib import Path

import aiofiles


async def write_json_atomic(file_path: Path, data: dict) -> None:
    """Write data as JSON to file_path atomically using tempfile + os.replace.

    Raises OSError if the write or replace fails.
    """
    dir_path = file_path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=str(dir_path))
    try:
        async with aiofiles.open(fd, mode="w", closefd=True) as f:
            await f.write(json.dumps(data, indent=2))
        os.replace(tmp_path, str(file_path))
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


async def read_json(file_path: Path) -> dict:
    """Read and parse a JSON file. Returns empty dict if file doesn't exist.

    Raises ValueError on malformed JSON (strict contract -- never silently fails).
    """
    if not file_path.exists():
        return {}

    async with aiofiles.open(file_path, mode="r") as f:
        content = await f.read()

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {file_path}: {exc}") from exc

    if not isinstance(result, dict):
        raise ValueError(f"Expected dict in {file_path}, got {type(result).__name__}")

    return result
