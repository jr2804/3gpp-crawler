"""Portal HTML parsing utilities."""

from __future__ import annotations

import logging
from decimal import Decimal

from bs4 import BeautifulSoup

from tdoc_crawler.tdocs.models import TDocMetadata

logger = logging.getLogger(__name__)


class PortalParsingError(Exception):
    """Raised when portal page parsing fails."""


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

    metadata: dict[str, str | None] = {}

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


__all__ = ["PortalParsingError", "parse_tdoc_portal_page"]
