"""3GPP Portal authentication and TDoc metadata parsing.

This module provides the PortalClient class as the primary interface for
interacting with the 3GPP portal. It consolidates:

- Session management and authentication
- TDoc URL extraction (unauthenticated)
- TDoc metadata fetching (authenticated)
- HTML parsing utilities

For backward compatibility, standalone functions are also provided that delegate
to PortalClient under the hood.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from tdoc_crawler.crawlers.constants import LOGIN_URL, PORTAL_BASE_URL, TDOC_DOWNLOAD_URL, TDOC_VIEW_URL
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.models.base import PortalCredentials
from tdoc_crawler.models.tdocs import TDocMetadata

logger = logging.getLogger(__name__)

# Common browser headers to avoid 403 Forbidden responses
_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class PortalAuthenticationError(Exception):
    """Raised when portal authentication fails."""


class PortalParsingError(Exception):
    """Raised when portal page parsing fails."""


class PortalSession:
    """Manages authenticated session with 3GPP portal.

    Note: This class is kept for backward compatibility. New code should use
    PortalClient which provides a unified interface.
    """

    def __init__(self, credentials: PortalCredentials, cache_dir: Path, cache_ttl: int = 7200, cache_refresh_on_access: bool = True, timeout: int = 30) -> None:
        """Initialize portal session.

        Args:
            credentials: ETSI Online Account credentials
            cache_dir: Directory for HTTP cache storage
            cache_ttl: HTTP cache TTL in seconds
            cache_refresh_on_access: Whether to refresh cache TTL on access
            timeout: Request timeout in seconds
        """
        self.credentials = credentials
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.session = create_cached_session(
            cache_dir=cache_dir,
            ttl=cache_ttl,
            refresh_ttl_on_access=cache_refresh_on_access,
            max_retries=3,
        )
        self._authenticated = False

        # Set browser-like headers to avoid 403 Forbidden
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def __enter__(self) -> PortalSession:
        """Enter context manager."""
        return self

    def __exit__(self, *args) -> None:
        """Exit context manager and close session."""
        self.session.close()

    def authenticate(self) -> None:
        """Authenticate with the 3GPP portal using EOL credentials.

        The portal uses JavaScript-based authentication via AJAX call to LoginEOL.ashx endpoint.
        We need to first visit the login page to establish a session, then call the AJAX endpoint.

        Raises:
            PortalAuthenticationError: If authentication fails
        """
        if self._authenticated:
            return

        logger.info("Authenticating with 3GPP portal...")

        # Step 1: Visit the login page to establish session and get cookies
        logger.debug("Visiting login page to establish session...")
        initial_response = self.session.get(LOGIN_URL, timeout=self.timeout)
        initial_response.raise_for_status()

        # Step 2: Call the AJAX login endpoint
        # The portal uses a JavaScript function that POSTs JSON to /ETSIPages/LoginEOL.ashx
        login_api_url = f"{PORTAL_BASE_URL}/ETSIPages/LoginEOL.ashx"

        # Build JSON payload matching the JavaScript login() function
        login_payload = {
            "username": self.credentials.username,
            "password": self.credentials.password,
        }

        logger.debug(f"Calling login API at {login_api_url}")

        # Submit login via AJAX API endpoint
        login_response = self.session.post(
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

        # Check response - the JavaScript checks if responseText == "Failed"
        response_text = login_response.text.strip()
        logger.debug(f"Login API response: {response_text}")

        if response_text.lower() == "failed":
            raise PortalAuthenticationError("Authentication failed - check credentials")

        # If response is not "Failed", authentication succeeded
        # The session cookies should now be set
        self._authenticated = True
        logger.info("Successfully authenticated with 3GPP portal")

    def fetch_tdoc_metadata(self, tdoc_id: str, url: str | None = None) -> TDocMetadata:
        """Fetch TDoc metadata from portal.

        Args:
            tdoc_id: TDoc identifier (e.g., 'S4-251364')
            url: Optional TDoc URL (if known)

        Returns:
            TDocMetadata instance with portal metadata

        Raises:
            PortalAuthenticationError: If authentication is required but fails
            PortalParsingError: If page parsing fails or TDoc not found
        """
        # If no URL provided, try to extract it from unauthenticated endpoint first
        if url is None:
            try:
                url = extract_tdoc_url_from_portal(tdoc_id, cache_dir=self.cache_dir, timeout=min(self.timeout, 15))
                logger.debug(f"Using URL extracted from unauthenticated endpoint for {tdoc_id}")
            except Exception as e:
                logger.debug(f"URL extraction failed for {tdoc_id}, using authenticated method: {e}")
                # Continue with authenticated method below

        # Ensure authenticated
        self.authenticate()

        # Fetch TDoc page
        view_url = f"{TDOC_VIEW_URL}?mode=view&contributionUid={tdoc_id}"
        logger.debug(f"Fetching TDoc metadata from {view_url}")

        response = self.session.get(view_url, timeout=self.timeout)
        response.raise_for_status()

        # Check if redirected to login (session expired)
        if "login.aspx" in response.url.lower():
            self._authenticated = False
            raise PortalAuthenticationError("Session expired - re-authentication required")

        # Parse the page
        return parse_tdoc_portal_page(response.text, tdoc_id, url)


def parse_tdoc_portal_page(html: str, tdoc_id: str, url: str | None = None) -> TDocMetadata:
    """Parse TDoc metadata from portal HTML page.

    Args:
        html: HTML content of the TDoc portal page
        tdoc_id: TDoc identifier for logging
        url: Optional TDoc URL (if known)

    Returns:
        TDocMetadata instance with portal metadata

    Raises:
        PortalParsingError: If TDoc not found, metadata table not found, or mandatory fields missing

    Expected fields:
        - meeting: Meeting identifier (required)
        - title: Document title (required)
        - contact: Contact person/organization (required)
        - source: Source organization (required)
        - tdoc_type: Document type classification (required)
        - for: Purpose (agreement, discussion, etc.) (required)
        - agenda_item: Associated agenda item (required)
        - status: Document status (optional)
        - is_revision_of: Reference to previous TDoc version (optional)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Check for "not found" or error messages
    error_indicators = [
        "not found",
        "does not exist",
        "invalid",
        "no document",
    ]
    page_text = soup.get_text().lower()
    if any(indicator in page_text for indicator in error_indicators):
        logger.warning(f"TDoc {tdoc_id} not found in portal")
        raise PortalParsingError(f"TDoc {tdoc_id} not found in portal")

    # Strategy: Find all label elements and their associated values
    metadata: dict[str, str | None] = {}

    # The metadata is parsed as follows:
    # - find the table <table class="ultimate3gpp" id="tableTdocGeneralTabView">...</table>
    # - iterate over table rows <tr>...</tr>
    # - each row contains two columns/cells: label and value
    # - label always ends with colon (:) - remove that
    # - store label as key (lower-case, trimmed, blanks replaced by underscores), trimmed value as value
    # - Keys of empty values (None or '') are not stored
    # - Special handling: The label "status" may be followed by additional download links in brackets, e.g.: "agreed(Download TDoc)"
    #   - We want to extract the main status text as key 'status'
    #   - Discard everything after the main status text (i.e., remove brackets and content within)
    # - Special handling: The value for label "Agenda item" is of form "7.1 - Some text":
    #   - We want to extract the numeric part ("7.1" - as string!) as key 'agenda_item_nbr'
    #   - We want to extract "the text" part ("Some text" - as string!) as key 'agenda_item_text'

    # Find the metadata table
    table = soup.find("table", {"class": "ultimate3gpp", "id": "tableTdocGeneralTabView"})
    if not table:
        logger.warning(f"Metadata table not found for TDoc {tdoc_id}")
        raise PortalParsingError(f"Metadata table not found for TDoc {tdoc_id}")

    # Iterate over table rows
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # Extract label from first cell
        label_cell = cells[0].get_text(strip=True)
        if not label_cell or not label_cell.endswith(":"):
            continue

        # Remove trailing colon and normalize label
        label = label_cell.rstrip(":").strip()
        label_key = label.lower().replace(" ", "_")

        # Extract value from second cell
        value = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        value = value.strip() if value else None

        # Skip empty values
        if not value:
            continue

        # Special handling for "status" field
        # Remove brackets and content within (e.g., "agreed(Download TDoc)" -> "agreed")
        if label_key == "status" and value:
            bracket_pos = value.find("(")
            if bracket_pos != -1:
                value = value[:bracket_pos].strip()

        # Store the value
        metadata[label_key] = value

        # Special handling for "Agenda item" field
        if label_key == "agenda_item" and value:
            # Parse "7.1 - Some text" format
            # Split by " - " to get number and text parts
            parts = value.split(" - ", 1)
            if len(parts) == 2:
                agenda_nbr = parts[0].strip()
                agenda_text = parts[1].strip()
                metadata["agenda_item_nbr"] = agenda_nbr
                metadata["agenda_item_text"] = agenda_text
            else:
                # No separator found, treat whole thing as number
                metadata["agenda_item_nbr"] = value

    # Check for mandatory fields
    mandatory_fields = ["meeting", "title", "contact", "source", "tdoc_type", "for", "agenda_item_nbr"]
    missing_fields = [field for field in mandatory_fields if field not in metadata or not metadata[field]]

    if missing_fields:
        error_msg = f"Missing mandatory fields for TDoc {tdoc_id}: {', '.join(missing_fields)}"
        logger.warning(error_msg)
        raise PortalParsingError(error_msg)

    # Create and return TDocMetadata instance
    # Note: meeting_id is not available from portal parsing, caller must resolve it
    return TDocMetadata(
        tdoc_id=tdoc_id,
        meeting_id=0,  # Placeholder - caller must resolve via meeting_name
        title=metadata.get("title", ""),
        url=url,
        source=metadata.get("source", ""),
        contact=metadata.get("contact", ""),
        tdoc_type=metadata.get("tdoc_type", "unknown"),
        for_purpose=metadata.get("for", "unknown"),
        agenda_item_nbr=Decimal(metadata.get("agenda_item_nbr", "0")),
        agenda_item_text=metadata.get("agenda_item_text", "Unknown"),
        status=metadata.get("status"),
        meeting_name=metadata.get("meeting"),
        is_revision_of=metadata.get("is_revision_of"),
        validated=True,
    )


def extract_tdoc_url_from_portal(tdoc_id: str, cache_dir: Path | None = None, timeout: int = 15) -> str:
    """Extract direct FTP download URL for a TDoc using unauthenticated DownloadTDoc.aspx endpoint.

    Args:
        tdoc_id: TDoc identifier (e.g., 'S4-251364')
        cache_dir: Directory for HTTP cache storage (optional)
        timeout: Request timeout in seconds (default 15 seconds)

    Returns:
        Direct FTP URL (e.g., 'https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_133-e/Docs/S4-251364.zip')

    Raises:
        PortalParsingError: If TDoc ID is invalid or URL extraction fails
        requests.RequestException: For network errors
    """
    logger.debug(f"Attempting to extract TDoc URL from DownloadTDoc endpoint for {tdoc_id}")

    # Build the URL for the DownloadTDoc endpoint
    download_url = f"{TDOC_DOWNLOAD_URL}?contributionUid={tdoc_id}"

    # Create a session with browser-like headers to avoid 403 Forbidden
    session = create_cached_session(cache_dir) if cache_dir is not None else requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    )

    try:
        # Fetch the DownloadTDoc page
        response = session.get(download_url, timeout=timeout)
        response.raise_for_status()

        # Check if the response contains an error message
        if "cannot be found" in response.text.lower() or "not found" in response.text.lower():
            raise PortalParsingError(f"TDoc {tdoc_id} not found on portal")

        # Extract URL from JavaScript redirect pattern
        # Pattern: window.location.href='https://www.3gpp.org/ftp/...'
        # The response may contain: javascript: window.location.href='https://www.3gpp.org/ftp/...';//]]>
        pattern = r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]"
        match = re.search(pattern, response.text)

        if not match:
            # Also try for the pattern in the CDATA section
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

        # Validate that the extracted URL is a proper URL format
        if not extracted_url.startswith(("http://", "https://", "ftp://")):
            raise PortalParsingError(f"Invalid URL format for TDoc {tdoc_id}: {extracted_url}")

        # Additional validation: check if the URL contains the TDoc ID (case-insensitive)
        if tdoc_id.lower() not in extracted_url.lower():
            logger.debug(f"Extracted URL for {tdoc_id} does not contain the TDoc ID: {extracted_url}")

        logger.debug(f"Successfully extracted TDoc URL for {tdoc_id}: {extracted_url}")
        return extracted_url

    except requests.RequestException as e:
        logger.error(f"Network error extracting URL for TDoc {tdoc_id}: {e}")
        raise
    except Exception as e:
        error_msg = f"Failed to extract URL for TDoc {tdoc_id}: {e}"
        logger.error(error_msg)
        raise PortalParsingError(error_msg) from e
    finally:
        session.close()


class PortalClient:
    """Unified 3GPP portal client with authentication and TDoc fetching.

    This class consolidates all portal-related functionality into a single interface:
    - Session management with browser headers
    - Authentication with EOL credentials
    - Unauthenticated TDoc URL extraction
    - Authenticated TDoc metadata fetching
    - HTML parsing utilities

    Example:
        >>> client = PortalClient(credentials=creds)
        >>> url = client.extract_tdoc_url("S4-251364")
        >>> metadata = client.fetch_tdoc_metadata("S4-251364", url)
    """

    def __init__(
        self,
        credentials: PortalCredentials | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 7200,
        cache_refresh_on_access: bool = True,
        timeout: int = 30,
    ) -> None:
        """Initialize portal client.

        Args:
            credentials: Optional credentials (required for full metadata fetching).
            cache_dir: Directory for HTTP cache storage.
            cache_ttl: Cache TTL in seconds.
            cache_refresh_on_access: Whether to refresh TTL on access.
            timeout: Request timeout in seconds.
        """
        self.credentials = credentials
        self.cache_dir = cache_dir or Path.home() / ".tdoc-crawler"
        self.timeout = timeout
        self._cache_ttl = cache_ttl
        self._cache_refresh_on_access = cache_refresh_on_access
        self._authenticated = False
        self._session: requests.Session | None = None

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
            PortalAuthenticationError: If authentication fails.
            ValueError: If no credentials were provided.
        """
        if self._authenticated:
            return

        if self.credentials is None:
            raise ValueError("Credentials required for authentication")

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
        logger.debug(f"Login API response: {response_text}")

        if response_text.lower() == "failed":
            raise PortalAuthenticationError("Authentication failed - check credentials")

        # Step 3: Store the authenticated session and copy cookies to cached session
        self._session = session
        self._authenticated = True
        logger.info("Successfully authenticated with 3GPP portal")

    def extract_tdoc_url(self, tdoc_id: str) -> str:
        """Extract direct FTP download URL for a TDoc (unauthenticated).

        Args:
            tdoc_id: TDoc identifier (e.g., 'S4-251364').

        Returns:
            Direct FTP/HTTPS URL for the TDoc download.

        Raises:
            PortalParsingError: If TDoc ID is invalid or URL extraction fails.
            requests.RequestException: For network errors.
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
            tdoc_id: TDoc identifier (e.g., 'S4-251364').
            url: Optional TDoc URL (if known, skips URL extraction).

        Returns:
            TDocMetadata instance with full portal metadata.

        Raises:
            PortalAuthenticationError: If authentication fails.
            PortalParsingError: If page parsing fails or TDoc not found.
            ValueError: If no credentials were provided.
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

        # Parse the page
        return self.parse_tdoc_page(response.text, tdoc_id, url)

    @staticmethod
    def parse_tdoc_page(html: str, tdoc_id: str, url: str | None = None) -> TDocMetadata:
        """Parse TDoc metadata from portal HTML page.

        This is a static method for cases where you have raw HTML content
        and want to parse it without making HTTP requests.

        Args:
            html: HTML content of the TDoc portal page.
            tdoc_id: TDoc identifier for logging.
            url: Optional TDoc URL (if known).

        Returns:
            TDocMetadata instance with portal metadata.

        Raises:
            PortalParsingError: If TDoc not found, metadata table not found, or mandatory fields missing.
        """
        return parse_tdoc_portal_page(html, tdoc_id, url)

    def _get_auth_session(self) -> requests.Session:
        """Get a non-cached session for authentication.

        Returns:
            Non-cached session with browser-like headers.
        """
        session = requests.Session()
        session.headers.update(_BROWSER_HEADERS)
        return session

    def _get_session(self) -> requests.Session:
        """Get or create a cached session with browser headers.

        Returns:
            Session configured with browser-like headers for portal access.
        """
        if self._session is None:
            self._session = create_cached_session(
                cache_dir=self.cache_dir,
                ttl=self._cache_ttl,
                refresh_ttl_on_access=self._cache_refresh_on_access,
                max_retries=3,
            )
            self._session.headers.update(_BROWSER_HEADERS)
        return self._session


def create_portal_client(
    credentials: PortalCredentials | None = None,
    cache_dir: Path | None = None,
    cache_ttl: int = 7200,
    cache_refresh_on_access: bool = True,
    timeout: int = 30,
) -> PortalClient:
    """Factory function to create a PortalClient instance.

    This is the recommended way to create a PortalClient for new code.

    Args:
        credentials: Optional credentials (required for full metadata).
        cache_dir: Directory for HTTP cache storage.
        cache_ttl: Cache TTL in seconds.
        cache_refresh_on_access: Whether to refresh TTL on access.
        timeout: Request timeout in seconds.

    Returns:
        Configured PortalClient instance.
    """
    return PortalClient(
        credentials=credentials,
        cache_dir=cache_dir,
        cache_ttl=cache_ttl,
        cache_refresh_on_access=cache_refresh_on_access,
        timeout=timeout,
    )
