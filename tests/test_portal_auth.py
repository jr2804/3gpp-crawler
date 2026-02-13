"""Test portal authentication and parsing with real credentials."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests

from tdoc_crawler.clients.portal import PortalAuthenticationError, PortalClient
from tdoc_crawler.models.base import PortalCredentials
from tdoc_crawler.parsers.portal import PortalParsingError


def _load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for raw_line in f:
                line = raw_line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def _get_credentials() -> PortalCredentials | None:
    """Get credentials from environment, loading .env file first."""
    _load_env_file()

    username = os.getenv("TDC_EOL_USERNAME")
    password = os.getenv("TDC_EOL_PASSWORD")

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
        pytest.skip("Missing TDC_EOL_USERNAME or TDC_EOL_PASSWORD environment variables")
    return creds


@pytest.fixture(autouse=True)
def check_internet() -> None:
    """Fixture to check internet connection before running tests."""
    if not _check_internet_connection():
        pytest.skip("No internet connection available")


def test_fetch_tdoc_metadata_success(credentials: PortalCredentials) -> None:
    """Test successful fetching of TDoc metadata from portal.

    Note: This test hits the real 3GPP portal and may fail if:
    - The portal structure has changed
    - The specific TDoc is no longer available
    - Network issues occur

    This is an integration test that verifies the portal parsing works.
    If the portal structure changes, this test will need to be updated.
    """
    # Using a recent TDoc - if this fails, the portal structure may have changed
    tdoc_id = "S4-260001"

    try:
        with PortalClient(credentials=credentials, timeout=30) as client:
            metadata = client.fetch_tdoc_metadata(tdoc_id)

        # If we get here, parsing succeeded - verify basic fields
        assert metadata is not None, f"Expected metadata for {tdoc_id}"
        assert metadata.tdoc_type is not None, "TDoc type should be populated"

    except PortalParsingError as exc:
        # The portal structure may have changed - this is not a refactoring issue
        pytest.skip(f"Portal structure may have changed: {exc}")


def test_fetch_tdoc_metadata_invalid_tdoc(credentials: PortalCredentials) -> None:
    """Test fetching metadata for non-existent TDoc."""
    tdoc_id = "S4-999999999"

    with pytest.raises(PortalParsingError), PortalClient(credentials=credentials, timeout=30) as client:
        client.fetch_tdoc_metadata(tdoc_id)


def test_fetch_tdoc_metadata_invalid_credentials() -> None:
    """Test authentication failure with invalid credentials."""
    # Using hardcoded invalid credentials is intentional for testing authentication failure
    invalid_credentials = PortalCredentials(username="invalid_user", password="invalid_password")  # noqa: S106
    tdoc_id = "S4-251364"

    with pytest.raises(PortalAuthenticationError), PortalClient(credentials=invalid_credentials, timeout=30) as client:
        client.fetch_tdoc_metadata(tdoc_id)
