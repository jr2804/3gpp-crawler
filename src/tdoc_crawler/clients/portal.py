"""3GPP Portal authentication and TDoc metadata fetching.

This module provides the PortalClient class as the primary interface for
interacting with the 3GPP portal. It consolidates:

- Session management and authentication
- TDoc URL extraction (unauthenticated)
- TDoc metadata fetching (authenticated)
- HTML parsing utilities (via parsers.portal module)

For backward compatibility, standalone functions are also provided.
"""

from __future__ import annotations

import re
from typing import Any

import niquests as requests

from tdoc_crawler.constants.urls import LOGIN_URL, PORTAL_BASE_URL, TDOC_DOWNLOAD_URL, TDOC_VIEW_URL
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.http_client import create_cached_session, resolve_ssl_verify
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import HttpCacheConfig, PortalCredentials
from tdoc_crawler.parsers.portal import PortalParsingError, parse_tdoc_portal_page
from tdoc_crawler.tdocs.models import TDocMetadata

logger = get_logger(__name__)


class PortalAuthenticationError(Exception):
    """Raised when portal authentication fails."""


class PortalCredentialsError(ValueError):
    """Raised when portal credentials are missing or invalid."""


class PortalClient:
    """Unified 3GPP portal client with authentication and TDoc fetching.

    This class consolidates all portal-related functionality into a single interface:
    - Session management with browser headers
    - Authentication with EOL credentials
    - Unauthenticated TDoc URL extraction
    - Authenticated TDoc metadata fetching
    - HTML parsing utilities (via parsers.portal module)

    Example:
        >>> from tdoc_crawler.models.base import PortalCredentials
        >>> creds = PortalCredentials(username="user", password="pass")
        >>> client = PortalClient(credentials=creds)
        >>> url = client.extract_tdoc_url("S4-251364")
        >>> metadata = client.fetch_tdoc_metadata("S4-251364", url)
    """

    def __init__(
        self,
        session: requests.Session | None = None,
        credentials: PortalCredentials | None = None,
        timeout: int = 30,
        http_cache: HttpCacheConfig | None = None,
        cache_manager_name: str | None = None,
        verify: bool | str | None = None,
    ) -> None:
        """Initialize portal client.

        Args:
            session: Optional requests.Session to reuse
            credentials: Optional portal credentials (if not provided, will attempt to resolve registered credentials)
            timeout: Request timeout in seconds
            http_cache: Optional HTTP cache configuration
            cache_manager_name: Optional cache manager name for resolving cache configuration
            verify: SSL certificate verification mode (bool or CA bundle path)
        """
        self._credentials = credentials
        self._cache_manager_name = cache_manager_name
        self.timeout = timeout
        self._http_cache = http_cache
        self._verify = verify
        self._authenticated = False
        self._session = session

    @property
    def credentials(self) -> PortalCredentials | None:
        """Return the credentials used by this client."""
        if self._credentials is None:
            # if not available, try to resolve registered credentials
            self._credentials = resolve_credentials(None, None)

        return self._credentials

    def close(self) -> None:
        """Close the underlying session if it exists."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> PortalClient:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager and close session."""
        self.close()

    def authenticate(self) -> None:
        """Authenticate with the 3GPP portal using EOL credentials.

        Raises:
            PortalAuthenticationError: If authentication fails
            PortalCredentialsError: If no credentials were provided
        """
        if self._authenticated:
            return

        if self.credentials is None:
            raise PortalCredentialsError("Portal credentials required for targeted fetch. Set TDC_EOL_USERNAME and TDC_EOL_PASSWORD.")

        logger.info("Authenticating with 3GPP portal...")

        # Use a non-cached session for authentication to avoid
        # hishel cache interfering with session cookies
        session = self._get_auth_session()

        # Step 1: Visit the login page to establish session and get cookies
        logger.debug("Visiting login page to establish session...")
        initial_response = session.get(LOGIN_URL, timeout=self.timeout)
        initial_response.raise_for_status()

        # Step 2: Call the AJAX login endpoint
        login_api_url = f"{PORTAL_BASE_URL}/ETSIPages/LoginEOL.ashx"
        login_payload = {
            "username": self.credentials.username,
            "password": self.credentials.password,
        }

        logger.debug(f"Calling login API at {login_api_url}")

        login_response = session.post(
            login_api_url,
            json=login_payload,
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": LOGIN_URL,
            },
            timeout=self.timeout,
        )
        login_response.raise_for_status()

        response_text = login_response.text.strip()
        # Step 3: store the authenticated session
        self._session = session
        self._authenticated = True

        if response_text.lower() == "failed":
            raise PortalAuthenticationError("Authentication failed - check credentials")

        # Step 3: Store the authenticated session
        self._session = session
        self._authenticated = True
        logger.info("Successfully authenticated with 3GPP portal")

    def extract_tdoc_url(self, tdoc_id: str) -> str:
        """Extract direct FTP download URL for a TDoc (unauthenticated).

        Args:
            tdoc_id: TDoc identifier (e.g., 'S4-251364')

        Returns:
            Direct FTP/HTTPS URL for the TDoc download

        Raises:
            PortalParsingError: If TDoc ID is invalid or URL extraction fails
            requests.RequestException: For network errors
        """
        logger.debug(f"Extracting TDoc URL from DownloadTDoc endpoint for {tdoc_id}")

        download_url = f"{TDOC_DOWNLOAD_URL}?contributionUid={tdoc_id}"
        session = self._get_session()

        try:
            response = session.get(download_url, timeout=self.timeout)
            response.raise_for_status()

            if "cannot be found" in response.text.lower() or "not found" in response.text.lower():
                raise PortalParsingError(f"TDoc {tdoc_id} not found on portal")

            # Extract URL from JavaScript redirect pattern
            pattern = r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]"
            match = re.search(pattern, response.text)

            if not match:
                # Try CDATA section pattern
                cdata_pattern = r"<!\[CDATA\[(.*?)\]\]>"
                cdata_matches = re.findall(cdata_pattern, response.text)
                for cdata_match in cdata_matches:
                    inner_match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", cdata_match)
                    if inner_match:
                        match = inner_match
                        break

            if not match:
                raise PortalParsingError(f"Failed to extract URL for TDoc {tdoc_id}: JavaScript redirect not found")

            extracted_url = match.group(1).strip()

            if not extracted_url.startswith(("http://", "https://", "ftp://")):
                raise PortalParsingError(f"Invalid URL format for TDoc {tdoc_id}: {extracted_url}")

            logger.debug(f"Successfully extracted TDoc URL for {tdoc_id}: {extracted_url}")
            return extracted_url

        except requests.RequestException:
            raise
        except PortalParsingError:
            raise
        except Exception as exc:
            error_msg = f"Failed to extract URL for TDoc {tdoc_id}: {exc}"
            logger.error(error_msg)
            raise PortalParsingError(error_msg) from exc

    def fetch_tdoc_metadata(self, tdoc_id: str, url: str | None = None) -> TDocMetadata:
        """Fetch full TDoc metadata from portal (requires authentication).

        Args:
            tdoc_id: TDoc identifier (e.g., 'S4-251364')
            url: Optional TDoc URL (if known, skips URL extraction)

        Returns:
            TDocMetadata instance with full portal metadata

        Raises:
            PortalAuthenticationError: If authentication fails
            PortalParsingError: If page parsing fails or TDoc not found
            PortalCredentialsError: If no credentials were provided
        """
        # Extract URL if not provided
        if url is None:
            try:
                url = self.extract_tdoc_url(tdoc_id)
                logger.debug(f"Using extracted URL for {tdoc_id}")
            except Exception as e:
                logger.debug(f"URL extraction failed for {tdoc_id}: {e}")
                # Continue - authenticated method can still work without pre-extracted URL

        # Ensure authenticated
        self.authenticate()

        # Fetch TDoc page
        view_url = f"{TDOC_VIEW_URL}?mode=view&contributionUid={tdoc_id}"
        logger.debug(f"Fetching TDoc metadata from {view_url}")

        session = self._get_session()
        response = session.get(view_url, timeout=self.timeout)
        response.raise_for_status()

        # Check if redirected to login (session expired)
        if "login.aspx" in response.url.lower():
            self._authenticated = False
            raise PortalAuthenticationError("Session expired - re-authentication required")

        # Parse the page using the parser module
        return self.parse_tdoc_page(response.text, tdoc_id, url)

    @staticmethod
    def parse_tdoc_page(html: str, tdoc_id: str, url: str | None = None) -> TDocMetadata:
        """Parse TDoc metadata from portal HTML page.

        This is a static method for cases where you have raw HTML content
        and want to parse it without making HTTP requests.

        Args:
            html: HTML content of the TDoc portal page
            tdoc_id: TDoc identifier for logging
            url: Optional TDoc URL (if known)

        Returns:
            TDocMetadata instance with portal metadata

        Raises:
            PortalParsingError: If TDoc not found, metadata table not found, or mandatory fields missing
        """
        return parse_tdoc_portal_page(html, tdoc_id, url)

    @property
    def _verify_resolved(self) -> bool | str:
        """Return effective SSL verification mode."""
        return resolve_ssl_verify(self._verify)

    def _get_session(self) -> requests.Session:
        """Get or create a cached session with browser headers.

        Returns:
            Session configured with browser-like headers for portal access
        """
        if self._session is None:
            self._session = create_cached_session(
                http_config=self._http_cache,
                cache_manager_name=self._cache_manager_name,
                verify=self._verify_resolved,
            )

        return self._session

    def _get_auth_session(self) -> requests.Session:
        """Get a non-cached session for authentication.

        Returns:
            Non-cached session with browser-like headers
        """
        return create_cached_session(http_cache_enabled=False, verify=self._verify_resolved)


__all__ = [
    "PortalAuthenticationError",
    "PortalClient",
]
