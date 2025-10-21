"""Test portal authentication and parsing with real credentials."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests

from tdoc_crawler.crawlers.portal import PortalAuthenticationError, fetch_tdoc_metadata
from tdoc_crawler.models.base import PortalCredentials


def _load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def _get_credentials() -> PortalCredentials | None:
    """Get credentials from environment, loading .env file first."""
    _load_env_file()

    username = os.getenv("EOL_USERNAME")
    password = os.getenv("EOL_PASSWORD")

    if not username or not password:
        return None

    return PortalCredentials(username=username, password=password)


def _check_internet_connection() -> bool:
    """Check if internet connection is available."""
    try:
        requests.get("https://www.3gpp.org", timeout=5)
    except requests.RequestException:
        return False
    else:
        return True


@pytest.fixture
def credentials() -> PortalCredentials:
    """Fixture to provide credentials, skipping test if not available."""
    creds = _get_credentials()
    if not creds:
        pytest.skip("Missing EOL_USERNAME or EOL_PASSWORD environment variables")
    return creds


@pytest.fixture(autouse=True)
def check_internet() -> None:
    """Fixture to check internet connection before running tests."""
    if not _check_internet_connection():
        pytest.skip("No internet connection available")


def test_fetch_tdoc_metadata_success(credentials: PortalCredentials) -> None:
    """Test successful fetching of TDoc metadata from portal."""
    tdoc_id = "S4-251364"

    metadata = fetch_tdoc_metadata(tdoc_id, credentials, timeout=30)

    assert metadata is not None, f"Expected metadata for {tdoc_id}"
    assert "meeting" in metadata
    assert "title" in metadata
    assert "contact" in metadata
    assert "tdoc_type" in metadata
    assert "for_purpose" in metadata
    assert "agenda_item" in metadata
    assert "status" in metadata

    # Check specific values we know about this TDoc
    assert metadata["meeting"] == "SA4#133-e"
    assert metadata["title"] == "UID"
    assert metadata["contact"] == "Jan Reimes"
    assert metadata["status"] == "agreed"


def test_fetch_tdoc_metadata_invalid_tdoc(credentials: PortalCredentials) -> None:
    """Test fetching metadata for non-existent TDoc."""
    tdoc_id = "S4-999999999"

    metadata = fetch_tdoc_metadata(tdoc_id, credentials, timeout=30)

    # Should return None for non-existent TDoc
    assert metadata is None


def test_fetch_tdoc_metadata_invalid_credentials() -> None:
    """Test authentication failure with invalid credentials."""
    # Using hardcoded invalid credentials is intentional for testing authentication failure
    invalid_credentials = PortalCredentials(username="invalid_user", password="invalid_password")  # noqa: S106
    tdoc_id = "S4-251364"

    with pytest.raises(PortalAuthenticationError):
        fetch_tdoc_metadata(tdoc_id, invalid_credentials, timeout=30)
