"""Portal HTML parsing utilities."""

from __future__ import annotations

import niquests as requests
from bs4 import BeautifulSoup, Tag

from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.parse import parse_agenda_item_nbr

logger = get_logger(__name__)


class PortalParser:
    """HTML parser for 3GPP portal TDoc pages.

    Wraps the standalone ``parse_tdoc_portal_page`` function with optional
    session injection for forward-compatibility with DI patterns.

    Args:
        session: Optional requests.Session to reuse for any HTTP operations.
            If not provided, one is created via ``create_cached_session()``
            on first use.

    Example:
        >>> parser = PortalParser()
        >>> metadata = parser.parse(html, "S4-251364")
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        """Initialize PortalParser.

        Args:
            session: Optional requests.Session. If None, a cached session is
                     created on first use via ``create_cached_session()``.
        """
        self._session = session

    @property
    def session(self) -> requests.Session:
        """Return the active session, creating one lazily if needed."""
        if self._session is None:
            self._session = create_cached_session()
        return self._session


class PortalParsingError(Exception):
    """Raised when portal page parsing fails."""


ERROR_INDICATORS: tuple[str, ...] = (
    "not found",
    "does not exist",
    "invalid",
    "no document",
)

MANDATORY_FIELDS: tuple[str, ...] = (
    "meeting",
    "title",
    "contact",
    "source",
    "tdoc_type",
    "for",
    "agenda_item_nbr",
)


def _validate_page_content(soup: BeautifulSoup, tdoc_id: str) -> None:
    """Raise when portal HTML looks like a missing-document page."""
    page_text = soup.get_text().lower()
    if any(indicator in page_text for indicator in ERROR_INDICATORS):
        logger.warning("TDoc %s not found in portal", tdoc_id)
        msg = f"TDoc {tdoc_id} not found in portal"
        raise PortalParsingError(msg)


def _get_metadata_table(soup: BeautifulSoup, tdoc_id: str) -> Tag:
    """Get TDoc metadata table from portal HTML."""
    table = soup.find("table", {"class": "ultimate3gpp", "id": "tableTdocGeneralTabView"})
    if not table:
        logger.warning("Metadata table not found for TDoc %s", tdoc_id)
        msg = f"Metadata table not found for TDoc {tdoc_id}"
        raise PortalParsingError(msg)
    return table


def _normalize_label(cells: list[Tag]) -> str | None:
    """Extract normalized key from first column label."""
    label_cell = cells[0].get_text(strip=True)
    if not label_cell or not label_cell.endswith(":"):
        return None
    label = label_cell.rstrip(":").strip()
    return label.lower().replace(" ", "_")


def _normalize_value(cells: list[Tag], label_key: str) -> str | None:
    """Extract normalized value from second column with status cleanup."""
    value = cells[1].get_text(strip=True) if len(cells) > 1 else ""
    value = value.strip() if value else None
    if not value:
        return None
    if label_key == "status":
        bracket_pos = value.find("(")
        if bracket_pos != -1:
            return value[:bracket_pos].strip()
    return value


def _store_agenda_fields(metadata: dict[str, str | None], value: str) -> None:
    """Split agenda item into number and text if separator is present."""
    parts = value.split(" - ", 1)
    if len(parts) == 2:
        metadata["agenda_item_nbr"] = parts[0].strip()
        metadata["agenda_item_text"] = parts[1].strip()
        return
    metadata["agenda_item_nbr"] = value


def _parse_metadata_table(table: Tag) -> dict[str, str | None]:
    """Parse metadata rows from portal table."""
    metadata: dict[str, str | None] = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label_key = _normalize_label(cells)
        if label_key is None:
            continue
        value = _normalize_value(cells, label_key)
        if value is None:
            continue
        metadata[label_key] = value
        if label_key == "agenda_item":
            _store_agenda_fields(metadata, value)
    return metadata


def _validate_mandatory_fields(metadata: dict[str, str | None], tdoc_id: str) -> None:
    """Ensure all required portal metadata fields are available."""
    missing_fields = [field for field in MANDATORY_FIELDS if field not in metadata or not metadata[field]]
    if missing_fields:
        error_msg = f"Missing mandatory fields for TDoc {tdoc_id}: {', '.join(missing_fields)}"
        logger.warning(error_msg)
        raise PortalParsingError(error_msg)


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

    _validate_page_content(soup, tdoc_id)
    table = _get_metadata_table(soup, tdoc_id)
    metadata = _parse_metadata_table(table)
    _validate_mandatory_fields(metadata, tdoc_id)

    agenda_item_value = metadata.get("agenda_item_nbr") or "0"
    return TDocMetadata(
        tdoc_id=tdoc_id,
        meeting_id=0,  # Placeholder - caller must resolve via meeting_name
        title=str(metadata.get("title") or ""),
        url=url,
        source=str(metadata.get("source") or ""),
        contact=str(metadata.get("contact") or ""),
        tdoc_type=str(metadata.get("tdoc_type") or "unknown"),
        for_purpose=str(metadata.get("for") or "unknown"),
        agenda_item_nbr=parse_agenda_item_nbr(agenda_item_value),
        agenda_item_text=str(metadata.get("agenda_item_text") or "Unknown"),
        status=metadata.get("status"),
        is_revision_of=metadata.get("is_revision_of"),
        file_size=None,
        date_created=None,
        validated=True,
        validation_failed=False,
    )


__all__ = ["PortalParser", "PortalParsingError", "parse_tdoc_portal_page"]
