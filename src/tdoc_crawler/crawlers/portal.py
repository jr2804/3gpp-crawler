"""3GPP Portal authentication and TDoc metadata parsing."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from tdoc_crawler.models.base import PortalCredentials

logger = logging.getLogger(__name__)

PORTAL_BASE_URL = "https://portal.3gpp.org"
TDOC_VIEW_URL = f"{PORTAL_BASE_URL}/ngppapp/CreateTdoc.Aspx"
LOGIN_URL = f"{PORTAL_BASE_URL}/login.aspx"


class PortalAuthenticationError(Exception):
    """Raised when portal authentication fails."""


class PortalParsingError(Exception):
    """Raised when portal page parsing fails."""


class PortalSession:
    """Manages authenticated session with 3GPP portal."""

    def __init__(self, credentials: PortalCredentials, timeout: int = 30) -> None:
        """Initialize portal session.

        Args:
            credentials: ETSI Online Account credentials
            timeout: Request timeout in seconds
        """
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()
        self._authenticated = False

        # Set browser-like headers to avoid 403 Forbidden
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

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

    def fetch_tdoc_metadata(self, tdoc_id: str) -> dict[str, str | None] | None:
        """Fetch TDoc metadata from portal.

        Args:
            tdoc_id: TDoc identifier (e.g., 'S4-251364')

        Returns:
            Dictionary with parsed metadata fields or None if TDoc not found

        Raises:
            PortalAuthenticationError: If authentication is required but fails
            PortalParsingError: If page parsing fails
        """
        # Ensure authenticated
        self.authenticate()

        # Fetch TDoc page
        url = f"{TDOC_VIEW_URL}?mode=view&contributionUid={tdoc_id}"
        logger.debug(f"Fetching TDoc metadata from {url}")

        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        # Check if redirected to login (session expired)
        if "login.aspx" in response.url.lower():
            self._authenticated = False
            raise PortalAuthenticationError("Session expired - re-authentication required")

        # Parse the page
        return parse_tdoc_portal_page(response.text, tdoc_id)


def parse_tdoc_portal_page(html: str, tdoc_id: str) -> dict[str, str | None] | None:
    """Parse TDoc metadata from portal HTML page.

    Args:
        html: HTML content of the TDoc portal page
        tdoc_id: TDoc identifier for logging

    Returns:
        Dictionary with parsed metadata fields or None if TDoc not found

    Expected fields:
        - meeting: Meeting identifier (required)
        - title: Document title (required)
        - contact: Contact person/organization (required)
        - tdoc_type: Document type classification (required)
        - for_purpose: Purpose (agreement, discussion, etc.) (required)
        - agenda_item: Associated agenda item (required)
        - status: Document status (required)
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
        return None

    # The portal page uses a form with labels and input/span elements
    # Strategy: Find all label elements and their associated values

    metadata: dict[str, str | None] = {
        "meeting": None,
        "title": None,
        "contact": None,
        "tdoc_type": None,
        "for_purpose": None,
        "agenda_item": None,
        "status": None,
        "is_revision_of": None,
    }

    # Find all table rows that might contain metadata
    # Common patterns:
    # 1. <label>Field Name</label> followed by <input> or <span>
    # 2. <td>Field Name</td><td>Value</td>

    # Try to find labels and their associated values
    labels = soup.find_all("label")
    for label in labels:
        label_text = label.get_text(strip=True).lower()

        # Find the associated input/span/select element
        # It might be:
        # - Next sibling
        # - In the same <td> parent
        # - Referenced by 'for' attribute

        value_element = None

        # Check 'for' attribute
        label_for = label.get("for")
        if label_for:
            value_element = soup.find(id=label_for)

        # If not found, check next siblings
        if not value_element:
            for sibling in label.find_next_siblings():
                if sibling.name in ("input", "select", "span", "div"):
                    value_element = sibling
                    break

        # If still not found, check parent and next sibling
        if not value_element and label.parent:
            next_td = label.parent.find_next_sibling("td")
            if next_td:
                value_element = next_td.find(["input", "select", "span", "div"])

        if not value_element:
            continue

        # Extract value
        value = None
        if value_element.name == "input":
            raw_value = value_element.get("value", "")
            value = str(raw_value).strip() if raw_value else None
        elif value_element.name == "select":
            selected = value_element.find("option", {"selected": True})
            value = selected.get_text(strip=True) if selected else None
        else:
            value = value_element.get_text(strip=True)

        if not value:
            continue

        # Map label text to metadata field
        if "meeting" in label_text:
            metadata["meeting"] = value
        elif "title" in label_text:
            metadata["title"] = value
        elif "contact" in label_text:
            metadata["contact"] = value
        elif "type" in label_text and "tdoc" in label_text:
            metadata["tdoc_type"] = value
        elif label_text.startswith("for") or "purpose" in label_text:
            metadata["for_purpose"] = value
        elif "agenda" in label_text:
            metadata["agenda_item"] = value
        elif "status" in label_text:
            metadata["status"] = value
        elif "revision" in label_text:
            metadata["is_revision_of"] = value

    # Also try table-based parsing (alternative structure)
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            label_cell = cells[0].get_text(strip=True).lower()
            value_cell = cells[1]

            # Extract value from cell
            value_input = value_cell.find(["input", "select", "span"])
            if value_input:
                if value_input.name == "input":
                    raw_value = value_input.get("value", "")
                    value = str(raw_value).strip() if raw_value else None
                elif value_input.name == "select":
                    selected = value_input.find("option", {"selected": True})
                    value = selected.get_text(strip=True) if selected else None
                else:
                    value = value_input.get_text(strip=True)
            else:
                value = value_cell.get_text(strip=True)

            if not value:
                continue

            # Map to metadata fields
            if "meeting" in label_cell:
                metadata["meeting"] = value
            elif "title" in label_cell:
                metadata["title"] = value
            elif "contact" in label_cell:
                metadata["contact"] = value
            elif "type" in label_cell:
                metadata["tdoc_type"] = value
            elif label_cell.startswith("for"):
                metadata["for_purpose"] = value
            elif "agenda" in label_cell:
                metadata["agenda_item"] = value
            elif "status" in label_cell:
                metadata["status"] = value
            elif "revision" in label_cell:
                metadata["is_revision_of"] = value

    # Clean up is_revision_of field if it contains a URL
    revision_value = metadata.get("is_revision_of")
    if revision_value:
        # If it's a URL like "CreateTDoc.aspx?mode=view&contributionId=...", skip it
        # We only want TDoc IDs like "S4-251363"
        if "CreateTDoc.aspx" in revision_value or "contributionId" in revision_value:
            # Try to extract TDoc ID from nearby text or skip
            metadata["is_revision_of"] = None
        elif not re.match(r"^[RSTC]\d+-\d+", revision_value, re.IGNORECASE):
            # Not a valid TDoc ID pattern, set to None
            metadata["is_revision_of"] = None

    # Validate required fields
    required_fields = ["meeting", "title", "contact", "tdoc_type", "for_purpose", "agenda_item", "status"]
    missing_fields = [field for field in required_fields if not metadata.get(field)]

    if missing_fields:
        logger.warning(f"TDoc {tdoc_id}: Missing required fields: {', '.join(missing_fields)}. Parsed: {metadata}")
        return None

    logger.debug(f"Successfully parsed metadata for TDoc {tdoc_id}")
    return metadata


def fetch_tdoc_metadata(
    tdoc_id: str,
    credentials: PortalCredentials,
    timeout: int = 30,
) -> dict[str, str | None] | None:
    """Fetch TDoc metadata from 3GPP portal (convenience function).

    Args:
        tdoc_id: TDoc identifier (e.g., 'S4-251364')
        credentials: ETSI Online Account credentials
        timeout: Request timeout in seconds

    Returns:
        Dictionary with parsed metadata fields or None if TDoc not found

    Raises:
        PortalAuthenticationError: If authentication fails
        PortalParsingError: If page parsing fails
    """
    with PortalSession(credentials, timeout) as session:
        return session.fetch_tdoc_metadata(tdoc_id)
