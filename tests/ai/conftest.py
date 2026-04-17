"""Pytest configuration and fixtures for AI tests."""

from __future__ import annotations

import hashlib
import importlib.util
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from tdoc_crawler.http_client import download_to_file

_TDOC_AI_AVAILABLE = True
if importlib.util.find_spec("threegpp_ai") is None:
    _TDOC_AI_AVAILABLE = False


@pytest.fixture(autouse=True)
def _require_tdoc_ai() -> None:
    """Skip AI tests when the optional 3gpp-ai package is unavailable."""
    if not _TDOC_AI_AVAILABLE:
        pytest.skip("3gpp-ai not installed")


def pytest_ignore_collect(collection_path: object, config: pytest.Config) -> bool:
    """Skip collecting AI tests when 3gpp-ai is unavailable."""
    return not _TDOC_AI_AVAILABLE


# URLs for downloading test data (fallback if files don't exist locally)
TEST_DATA_URLS = [
    # "https://www.3gpp.org/ftp/Specs/archive/26_series/26.253/26253-j10.zip",
    "https://www.3gpp.org/ftp/Specs/archive/26_series/26.260/26260-j10.zip",
    "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_135_India/Docs/S4-260001.zip",
    "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_135_India/Docs/S4-260002.zip",
    "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_135_India/Docs/S4-260003.zip",
    "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_132_Fukuoka/Inbox/S4-251003.zip",
    "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_134_Dallas/Inbox/S4-251971.zip",
]


def _extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """Extract ZIP file to target directory."""
    print(f"Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"Extracted to {extract_dir.name}")


def _create_broken_docx(target_path: Path) -> None:
    """Create a broken DOCX file (just text content)."""
    print("Creating broken.docx...")
    target_path.write_text("broken")
    print(f"Created {target_path.name}")


def _file_exists_and_valid(file_path: Path, expected_hash: str | None = None) -> bool:
    """Check if file exists and optionally verify its hash."""
    if not file_path.exists():
        return False

    if expected_hash:
        # Calculate SHA256 hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest() == expected_hash

    return True


def prepare_ai_test_files(data_dir: Path) -> None:
    """Prepare AI test files by copying and extracting required data.

    Only copies/extracts files that don't already exist.
    """
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create broken.docx if it doesn't exist
    broken_docx_path = data_dir / "broken.docx"
    if not _file_exists_and_valid(broken_docx_path):
        _create_broken_docx(broken_docx_path)

    # Copy and extract ZIP files from source directory
    for url in TEST_DATA_URLS:
        zip_filename = url.split("/")[-1]
        zip_file = data_dir / zip_filename
        sub_dir = data_dir / zip_filename.replace(".zip", "")
        if sub_dir.exists():
            print(f"{sub_dir.name} already exists, skipping")
            continue

        # Skip if target ZIP file already exists
        if not zip_file.exists():
            download_to_file(url, zip_file, http_cache_enabled=False)

        _extract_zip(zip_file, sub_dir)


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Return path to test data directory for AI tests."""
    data_dir = Path(__file__).parent / "data"

    # Prepare test files if they don't exist
    prepare_ai_test_files(data_dir)

    return data_dir


@pytest.fixture
def mock_storage() -> MagicMock:
    """Return a mock storage object for testing.

    This fixture provides a MagicMock instance that can be used
    as a storage backend in AI pipeline and extraction tests.
    """
    mock = MagicMock()
    mock.get_status.return_value = None
    mock.query_graph.return_value = ([], [])
    return mock


@pytest.fixture
def runner() -> CliRunner:
    """Return a CLI runner for testing AI commands.

    This fixture provides a Click CliRunner instance for
    testing the AI CLI commands.
    """
    return CliRunner()


@pytest.fixture(autouse=True)
def reset_ai_service_container() -> None:
    """No-op fixture for backward compatibility.

    This fixture was previously used to reset the AiServiceContainer singleton.
    With the refactored design, no singleton exists, so this is a no-op.
    """
    return  # No cleanup needed - no singleton
