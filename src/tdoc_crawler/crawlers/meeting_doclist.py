"""Meeting-based TDoc document list fetcher for credential-free metadata retrieval."""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from tdoc_crawler.http_client import create_cached_session

if TYPE_CHECKING:
    from tdoc_crawler.models.tdocs import TDocMetadata

logger = logging.getLogger(__name__)


class DocumentListError(Exception):
    """Raised when document list fetching or parsing fails."""


def fetch_meeting_document_list(
    meeting_id: int,
    cache_dir: Path,
    cache_ttl: int = 7200,
    cache_refresh_on_access: bool = True,
    timeout: int = 30,
) -> list[TDocMetadata]:
    """Fetch all TDoc metadata for a meeting via document list Excel file.

    Args:
        meeting_id: 3GPP meeting identifier
        cache_dir: Directory for HTTP cache storage
        cache_ttl: HTTP cache TTL in seconds
        cache_refresh_on_access: Whether to refresh cache TTL on access
        timeout: Request timeout in seconds

    Returns:
        List of TDocMetadata instances for all TDocs in the meeting

    Raises:
        DocumentListError: If document list cannot be fetched or parsed
    """
    # Construct document list URL
    doclist_url = f"https://portal.3gpp.org/ngppapp/GenerateDocumentList.aspx?meetingId={meeting_id}"
    logger.debug(f"Fetching document list for meeting {meeting_id} from {doclist_url}")

    # Create cached session (no credentials required)
    session = create_cached_session(
        cache_dir=cache_dir,
        ttl=cache_ttl,
        refresh_ttl_on_access=cache_refresh_on_access,
        max_retries=3,
    )

    try:
        # Download Excel file
        logger.debug(f"Downloading Excel document list for meeting {meeting_id}")
        response = session.get(doclist_url, timeout=timeout)
        response.raise_for_status()

        # Check if we got a valid Excel file
        content_type = response.headers.get("content-type", "").lower()
        if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in content_type:
            # Some responses might not set content-type correctly, check file signature
            if not response.content.startswith(b"PK"):
                raise DocumentListError(f"Expected Excel file for meeting {meeting_id}, got content-type: {content_type}")

        # Parse Excel file
        logger.debug(f"Parsing Excel document list for meeting {meeting_id}")
        return parse_excel_document_list(response.content, meeting_id)

    except Exception as exc:
        if isinstance(exc, DocumentListError):
            raise
        logger.warning(f"Failed to fetch document list for meeting {meeting_id}: {exc}")
        raise DocumentListError(f"Failed to fetch document list for meeting {meeting_id}: {exc}") from exc
    finally:
        session.close()


def parse_excel_document_list(
    excel_content: bytes,
    meeting_id: int,
) -> list[TDocMetadata]:
    """Parse Excel document list and convert to TDocMetadata instances.

    Args:
        excel_content: Raw Excel file content
        meeting_id: Meeting ID for reference

    Returns:
        List of TDocMetadata instances
    """
    try:
        # Use pandas with python-calamine engine for fast Excel parsing
        df = pd.read_excel(
            io.BytesIO(excel_content),
            engine="calamine",
            sheet_name="TDoc_List",
        )

        logger.debug(f"Found {len(df)} rows in TDoc_List sheet for meeting {meeting_id}")

        # Convert DataFrame rows to TDocMetadata instances
        tdoc_metadata_list = []
        for index, row in df.iterrows():
            try:
                tdoc_metadata = convert_excel_row_to_tdoc_metadata(row, meeting_id)
                if tdoc_metadata:
                    tdoc_metadata_list.append(tdoc_metadata)
                else:
                    logger.debug(f"Skipping row {index + 1}: missing required TDoc ID")
            except Exception as exc:
                logger.warning(f"Failed to parse row {index + 1} for meeting {meeting_id}: {exc}")
                continue

        logger.info(f"Successfully parsed {len(tdoc_metadata_list)} TDoc metadata entries for meeting {meeting_id}")
        return tdoc_metadata_list

    except Exception as exc:
        raise DocumentListError(f"Failed to parse Excel document list for meeting {meeting_id}: {exc}") from exc


def convert_excel_row_to_tdoc_metadata(
    row: pd.Series,
    meeting_id: int,
) -> TDocMetadata | None:
    """Convert a single Excel row to TDocMetadata.

    Args:
        row: pandas Series representing one Excel row
        meeting_id: Meeting ID for reference

    Returns:
        TDocMetadata instance or None if conversion fails
    """
    from tdoc_crawler.models.tdocs import TDocMetadata

    # Map Excel columns to TDocMetadata fields
    # Try multiple possible column names to handle different Excel formats
    tdoc_id = _extract_tdoc_id(row)
    if not tdoc_id:
        return None

    # Extract other fields with fallbacks
    title = _get_column_value(row, ["Title", "Document Title", "Description", "Subject"])
    tdoc_type = _get_column_value(row, ["Type", "Document Type", "TDoc Type"])
    for_purpose = _get_column_value(row, ["For", "Purpose", "For Purpose"])
    source = _get_column_value(row, ["Source", "Organization", "Company"])
    contact = _get_column_value(row, ["Contact", "Contact Person", "Author"])
    agenda_item = _get_column_value(row, ["Agenda Item", "Agenda", "Agenda Ref"])
    status = _get_column_value(row, ["Status", "Document Status"])
    is_revision_of = _get_column_value(row, ["Revision of", "Is Revision of", "Based on"])
    date_created = _get_column_value(row, ["Date", "Created", "Date Created", "Submission Date"])

    # Generate URL (this will be validated/updated later by the directory crawler)
    url = f"https://www.3gpp.org/ftp/tsg_ran/.../{tdoc_id.upper()}.zip"

    now = datetime.now(UTC)

    try:
        # Parse agenda item number
        agenda_nbr, agenda_text = _parse_agenda_item(agenda_item)

        # Parse date
        parsed_date = _parse_date(date_created)

        return TDocMetadata(
            tdoc_id=tdoc_id.upper(),
            meeting_id=meeting_id,
            title=title or "Unknown Title",
            url=url,
            source=source or "Unknown",
            contact=contact or "Unknown",
            tdoc_type=tdoc_type or "unknown",
            for_purpose=for_purpose or "unknown",
            agenda_item_nbr=agenda_nbr,
            agenda_item_text=agenda_text,
            status=status,
            meeting_name=None,  # Will be resolved from meeting database
            is_revision_of=is_revision_of,
            file_size=None,  # Not available in Excel
            date_created=parsed_date,
            date_retrieved=now,
            date_updated=now,
            validated=True,  # Direct from portal, no validation needed
            validation_failed=False,
        )

    except Exception as exc:
        logger.debug(f"Failed to create TDocMetadata for {tdoc_id}: {exc}")
        return None


def _extract_tdoc_id(row: pd.Series) -> str | None:
    """Extract TDoc ID from Excel row.

    Args:
        row: pandas Series representing one Excel row

    Returns:
        TDoc ID string or None if not found
    """
    # Try multiple possible column names for TDoc ID
    tdoc_id_columns = ["TDoc", "Contribution", "Document", "TDoc ID", "Contribution ID", "ID", "Number", "TDoc Number", "Contribution Number"]

    for col in tdoc_id_columns:
        value = row.get(col)
        if value and isinstance(value, str):
            tdoc_id = value.strip()
            # Validate TDoc ID format
            if _is_valid_tdoc_id(tdoc_id):
                return tdoc_id

    return None


def _is_valid_tdoc_id(tdoc_id: str) -> bool:
    """Check if string is a valid TDoc ID format.

    Args:
        tdoc_id: String to validate

    Returns:
        True if valid TDoc ID format
    """
    import re

    # TDoc ID pattern: [RSC][1-6P] followed by 4-10 chars
    pattern = re.compile(r"^[RSC][1-6P].{4,10}$", re.IGNORECASE)
    return bool(pattern.match(tdoc_id.strip()))


def _get_column_value(row: pd.Series, possible_names: list[str]) -> str | None:
    """Get value from row using possible column names.

    Args:
        row: pandas Series representing one Excel row
        possible_names: List of possible column names

    Returns:
        Column value or None if not found
    """
    for col_name in possible_names:
        value = row.get(col_name)
        if value and isinstance(value, str):
            return value.strip()
        elif value is not None:
            # Handle non-string values (dates, numbers, etc.)
            return str(value).strip()
    return None


def _parse_agenda_item(agenda_item: str | None) -> tuple[Decimal, str]:
    """Parse agenda item into number and text components.

    Args:
        agenda_item: Agenda item string (e.g., "7.1 - Some text" or just "7.1")

    Returns:
        Tuple of (agenda_number, agenda_text)
    """
    if not agenda_item:
        return Decimal("0.0"), "Unknown"

    # Try to split by " - " to get number and text
    parts = agenda_item.split(" - ", 1)
    if len(parts) == 2:
        agenda_nbr_str = parts[0].strip()
        agenda_text = parts[1].strip()
    else:
        # No separator found, treat whole thing as number
        agenda_nbr_str = agenda_item.strip()
        agenda_text = "Unknown"

    # Parse agenda number as Decimal
    try:
        agenda_nbr = Decimal(agenda_nbr_str)
    except Exception:
        agenda_nbr = Decimal("0.0")

    return agenda_nbr, agenda_text


def _parse_date(date_value: str | None) -> datetime | None:
    """Parse date from Excel value.

    Args:
        date_value: Date value from Excel

    Returns:
        datetime object or None if parsing fails
    """
    if not date_value:
        return None

    try:
        # Handle different date formats
        if isinstance(date_value, datetime):
            return date_value
        elif isinstance(date_value, str):
            # Try common date formats
            formats = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
        return None

    except Exception:
        return None


__all__ = [
    "DocumentListError",
    "fetch_meeting_document_list",
    "parse_excel_document_list",
    "convert_excel_row_to_tdoc_metadata",
]
