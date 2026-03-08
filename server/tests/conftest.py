import pytest
from pathlib import Path


@pytest.fixture
def tmp_shared_folder(tmp_path: Path) -> Path:
    """Create a temporary shared folder with sample files for testing.

    Structure:
        tmp_path/
            test.txt          (contains "hello world")
            subdir/
                nested.txt    (contains "nested content")
            empty_dir/
    """
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    nested_file = subdir / "nested.txt"
    nested_file.write_text("nested content")

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    return tmp_path
