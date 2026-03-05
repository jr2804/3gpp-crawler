"""Test configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Provide a temporary cache directory for tests."""
    return tmp_path / ".cache"


@pytest.fixture
def test_data_dir() -> Path:
    """Provide path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"
