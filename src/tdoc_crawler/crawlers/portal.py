"""3GPP Portal authentication and TDoc metadata parsing."""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from tdoc_crawler.crawlers.constants import (LOGIN_URL, PORTAL_BASE_URL,

if TYPE_CHECKING:
    from tdoc_crawler.models.base import PortalCredentials
    from tdoc_crawler.models.tdocs import TDocMetadata

logger = logging.getLogger(__name__)


class PortalAuthenticationError(Exception):
    """Raised when portal authentication fails."""


class PortalParsingError(Exception):
    """Raised when portal page parsing fails."""


class PortalSession:
    """Manages authenticated session with 3GPP portal."""

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
    from tdoc_crawler.models.tdocs import TDocMetadata

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

    # Generate URL if not provided
    if url is None:
        url = f"https://www.3gpp.org/ftp/tsg_ran/.../{tdoc_id.upper()}.zip"

    # Parse agenda_item_nbr as Decimal
    try:
        agenda_nbr_decimal = Decimal(str(metadata["agenda_item_nbr"]))
    except Exception as exc:
        error_msg = f"Invalid agenda item number '{metadata['agenda_item_nbr']}' for TDoc {tdoc_id}: {exc}"
        logger.warning(error_msg)
        raise PortalParsingError(error_msg) from exc

    # Create TDocMetadata instance
    # At this point we've validated all mandatory fields exist and are not None
    try:
        tdoc_metadata = TDocMetadata(
            tdoc_id=tdoc_id.upper(),
            meeting_id=0,  # Will be resolved later from meeting_name
            meeting_name=metadata.get("meeting"),  # Store original meeting name for resolution
            title=str(metadata["title"]),
            url=url,
            source=str(metadata["source"]),
            contact=str(metadata["contact"]),
            tdoc_type=str(metadata.get("tdoc_type", "unknown")),
            for_purpose=str(metadata.get("for", "unknown")),
            agenda_item_nbr=agenda_nbr_decimal,
            agenda_item_text=str(metadata.get("agenda_item_text", "Unknown")),
            status=metadata.get("status"),
            is_revision_of=metadata.get("is_revision_of"),
            file_size=None,
            date_created=None,
            validated=True,
            validation_failed=False,
        )
        logger.debug(f"Successfully parsed metadata for TDoc {tdoc_id}")
        return tdoc_metadata

    except Exception as exc:
        error_msg = f"Failed to create TDocMetadata for TDoc {tdoc_id}: {exc}"
        logger.warning(error_msg)
        raise PortalParsingError(error_msg) from exc


def fetch_tdoc_metadata(
    tdoc_id: str,
    credentials: PortalCredentials,
    cache_dir: Path,
    cache_ttl: int = 7200,
    cache_refresh_on_access: bool = True,
    timeout: int = 30,
    url: str | None = None,
) -> TDocMetadata:
    """Fetch TDoc metadata from 3GPP portal (convenience function).

    Args:
        tdoc_id: TDoc identifier (e.g., 'S4-251364')
        credentials: ETSI Online Account credentials
        cache_dir: Directory for HTTP cache storage
        cache_ttl: HTTP cache TTL in seconds
        cache_refresh_on_access: Whether to refresh cache TTL on access
        timeout: Request timeout in seconds
        url: Optional TDoc URL (if known)

    Returns:
        TDocMetadata instance with portal metadata

    Raises:
        PortalAuthenticationError: If authentication fails
        PortalParsingError: If page parsing fails or TDoc not found
    """
    with PortalSession(credentials, cache_dir, cache_ttl, cache_refresh_on_access, timeout) as session:
        return session.fetch_tdoc_metadata(tdoc_id, url)
