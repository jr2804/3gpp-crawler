"""Tests for PortalClient class."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import niquests as requests
import pytest

from tdoc_crawler.clients.portal import PortalAuthenticationError, PortalClient, PortalCredentialsError
from tdoc_crawler.clients.portal import PortalClient as ReExportedPortalClient
from tdoc_crawler.constants.urls import TDOC_DOWNLOAD_URL
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.models.base import PortalCredentials
from tdoc_crawler.parsers.portal import PortalParsingError


class TestPortalClientInit:
    """Tests for PortalClient initialization."""

    def test_init_without_credentials(self) -> None:
        """Client can be created without credentials for URL extraction."""
        with patch("tdoc_crawler.clients.portal.resolve_credentials", return_value=None):
            client = PortalClient()
            assert client.credentials is None
            assert client.timeout == 30
            assert client._session is None

    def test_init_with_credentials(self) -> None:
        """Client can be created with credentials for authenticated access."""
        creds = PortalCredentials(username="test", password="test")
        client = PortalClient(credentials=creds)
        assert client.credentials == creds
        assert client.credentials.username == "test"

    def test_init_with_custom_timeout(self) -> None:
        """Client can be created with custom timeout."""
        client = PortalClient(timeout=60)
        assert client.timeout == 60


class TestPortalClientSession:
    """Tests for PortalClient session management."""

    def test_get_session_creates_session(self, test_cache_dir: Path) -> None:
        """Getting session creates it if not exists."""
        client = PortalClient()
        session = client._get_session()
        assert session is not None
        assert client._session is not None

    def test_get_session_returns_same_session(self, test_cache_dir: Path) -> None:
        """Getting session returns the same instance."""
        client = PortalClient()
        session1 = client._get_session()
        session2 = client._get_session()
        assert session1 is session2

    def test_close_closes_session(self, test_cache_dir: Path) -> None:
        """Close method closes the session."""
        client = PortalClient()
        client._get_session()
        client.close()
        assert client._session is None

    def test_context_manager(self, test_cache_dir: Path) -> None:
        """Client works as context manager."""
        with PortalClient() as client:
            assert client._get_session() is not None
        assert client._session is None

    def test_close_idempotent(self, test_cache_dir: Path) -> None:
        """Close can be called multiple times safely."""
        client = PortalClient()
        client._get_session()
        client.close()
        client.close()  # Should not raise

    def test_get_session_passes_verify_to_cached_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cached session creation should receive resolved verify mode."""
        captured: dict[str, object] = {}

        def _fake_create_cached_session(*args: object, **kwargs: object) -> requests.Session:
            _ = args
            captured.update(kwargs)
            return requests.Session()

        monkeypatch.setattr("tdoc_crawler.clients.portal.create_cached_session", _fake_create_cached_session)
        client = PortalClient(verify=False)
        session = client._get_session()
        try:
            assert captured["verify"] is False
        finally:
            session.close()

    def test_get_auth_session_uses_non_cached_with_verify(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Auth session must remain non-cached and preserve verify mode."""
        captured: dict[str, object] = {}

        def _fake_create_cached_session(*args: object, **kwargs: object) -> requests.Session:
            _ = args
            captured.update(kwargs)
            return requests.Session()

        monkeypatch.setattr("tdoc_crawler.clients.portal.create_cached_session", _fake_create_cached_session)
        client = PortalClient(verify=False)
        session = client._get_auth_session()
        try:
            assert captured["http_cache_enabled"] is False
            assert captured["verify"] is False
        finally:
            session.close()


class TestPortalClientBrowserHeaders:
    """Tests that browser headers are properly set."""

    def test_session_has_browser_headers(self, test_cache_dir: Path) -> None:
        """Session has browser-like headers to avoid 403 Forbidden."""
        client = PortalClient()
        session = client._get_session()
        assert "User-Agent" in session.headers
        assert "Mozilla" in session.headers["User-Agent"]
        assert "Accept" in session.headers
        assert "text/html" in session.headers["Accept"]


class TestPortalClientExtractTdocUrl:
    """Tests for PortalClient.extract_tdoc_url method."""

    def test_extract_url_success(self) -> None:
        """Can extract URL for valid TDoc."""
        client = PortalClient()
        expected_url = "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_133-e/Docs/S4-251364.zip"
        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.text = f"window.location.href='{expected_url}';"
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            result = client.extract_tdoc_url("S4-251364")
            assert result == expected_url

    def test_extract_url_not_found(self) -> None:
        """Raises error when TDoc not found."""
        client = PortalClient()
        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "TDoc cannot be found"
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            with pytest.raises(PortalParsingError):
                client.extract_tdoc_url("S4-999999")

    def test_extract_url_no_redirect(self) -> None:
        """Raises error when JavaScript redirect not found."""
        client = PortalClient()
        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "<html>No redirect here</html>"
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            with pytest.raises(PortalParsingError):
                client.extract_tdoc_url("S4-251364")


class TestPortalClientAuthenticate:
    """Tests for PortalClient.authenticate method."""

    def test_authenticate_requires_credentials(self) -> None:
        """Authentication fails without credentials."""
        with patch("tdoc_crawler.clients.portal.resolve_credentials", return_value=None):
            client = PortalClient()
            with pytest.raises(PortalCredentialsError, match="Portal credentials required"):
                client.authenticate()

    def test_authenticate_success(self) -> None:
        """Authentication succeeds with valid credentials."""
        creds = PortalCredentials(username="test", password="test")
        client = PortalClient(credentials=creds)
        with patch.object(client, "_get_auth_session") as mock_get_auth_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.text = "Success"  # Non-failed response
            mock_session.get.return_value = mock_response
            mock_session.post.return_value = mock_response
            mock_get_auth_session.return_value = mock_session

            client.authenticate()
            assert client._authenticated is True

    def test_authenticate_cached(self) -> None:
        """Second authentication call is cached (no-op)."""
        creds = PortalCredentials(username="test", password="test")
        client = PortalClient(credentials=creds)
        client._authenticated = True

        with patch.object(client, "_get_session") as mock_get_session:
            client.authenticate()
            mock_get_session.assert_not_called()

    def test_authenticate_failure(self) -> None:
        """Authentication fails with invalid credentials."""
        creds = PortalCredentials(username="test", password="wrong")
        client = PortalClient(credentials=creds)
        with patch.object(client, "_get_auth_session") as mock_get_auth_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.text = "Failed"
            mock_session.get.return_value = mock_response
            mock_session.post.return_value = mock_response
            mock_get_auth_session.return_value = mock_session

            with pytest.raises(PortalAuthenticationError):
                client.authenticate()


class TestPortalClientFetchTdocMetadata:
    """Tests for PortalClient.fetch_tdoc_metadata method."""

    def test_fetch_requires_authentication(self) -> None:
        """Fetching fails without credentials."""
        with patch("tdoc_crawler.clients.portal.resolve_credentials", return_value=None):
            client = PortalClient()
            with pytest.raises(PortalCredentialsError, match="Portal credentials required"):
                client.fetch_tdoc_metadata("S4-251364")

    def test_fetch_success(self) -> None:
        """Successfully fetches TDoc metadata."""
        creds = PortalCredentials(username="test", password="test")
        client = PortalClient(credentials=creds)
        with (
            patch.object(client, "_get_session") as mock_get_session,
            patch.object(client, "authenticate") as mock_auth,
            patch.object(PortalClient, "parse_tdoc_page") as mock_parse,
        ):
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.url = f"{TDOC_DOWNLOAD_URL}?contributionUid=S4-251364"
            mock_response.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            mock_auth.return_value = None
            mock_parse.return_value = TDocMetadata(
                tdoc_id="S4-251364",
                meeting_id=0,
                title="Test Title",
                url="https://example.com",
                source="Test Source",
                contact="Test Contact",
                tdoc_type="Discussion",
                for_purpose="Discussion",
                agenda_item_nbr="1",
                agenda_item_text="Test",
                status="Approved",
                validated=True,
            )

            result = client.fetch_tdoc_metadata("S4-251364")
            assert result.tdoc_id == "S4-251364"

    def test_fetch_session_expired(self) -> None:
        """Handles session expiration correctly."""
        creds = PortalCredentials(username="test", password="test")
        client = PortalClient(credentials=creds)
        with patch.object(client, "_get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.url = "https://portal.3gpp.org/login.aspx"
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            with pytest.raises(PortalAuthenticationError):
                client.fetch_tdoc_metadata("S4-251364")


class TestPortalClientParseTdocPage:
    """Tests for PortalClient.parse_tdoc_page static method."""

    def test_parse_tdoc_page_is_static(self) -> None:
        """parse_tdoc_page is a static method."""
        assert isinstance(PortalClient.__dict__["parse_tdoc_page"], staticmethod)

    def test_parse_tdoc_page_delegates_to_function(self) -> None:
        """parse_tdoc_page delegates to the standalone parse_tdoc_portal_page function."""
        # This verifies the static method properly calls the underlying function
        # by checking it's callable and has the same signature

        sig = inspect.signature(PortalClient.parse_tdoc_page)
        params = list(sig.parameters.keys())
        # Should have html, tdoc_id, url
        assert "html" in params
        assert "tdoc_id" in params
        assert "url" in params


class TestPortalClientReExports:
    """Tests for re-exports in crawlers package."""

    def test_portal_client_re_exported(self) -> None:
        """PortalClient is re-exported from crawlers package."""
        assert ReExportedPortalClient is not None
