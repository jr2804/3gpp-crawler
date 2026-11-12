"""Meeting Document List TDoc metadata source.

This module provides a TDocSource implementation that fetches metadata
from 3GPP meeting document list Excel files (unauthenticated).
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import niquests as requests
import pandas as pd

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.constants.urls import DOCLIST_URL_TEMPLATE, PORTAL_BASE_URL
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.sources.base import TDocSource, TDocSourceConfig
from tdoc_crawler.utils.parse import AgendaItemNumber, parse_agenda_item_nbr

_RELATED_WI_COLUMNS: Final[tuple[str, ...]] = ("Related WIs", "Related WI", "Related Work Items")
_WI_SEPARATORS = re.compile(r"[,;]")
_WI_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
_WI_PLACEHOLDERS: Final[frozenset[str]] = frozenset({"NONE", "NULL", "NA", "N/A", "NAN", "-"})

_logger = get_logger(__name__)


class DocumentListError(Exception):
    """Raised when document list fetching or parsing fails."""


class DocumentListSource(TDocSource):
    """TDoc metadata source using meeting document lists.

    This source provides unauthenticated bulk access to all TDocs in a meeting
    by downloading and parsing the Excel document list. It's ideal for fetching
    all metadata for a specific meeting efficiently without credentials.
    """

    def __init__(
        self,
        config: TDocSourceConfig,
    ) -> None:
        """Initialize document list source.

        Args:
            config: Source configuration
        """
        self.config = config

    def fetch_by_id(
        self,
        tdoc_id: str,
        *,
        db_file: Path | None = None,
        timeout: int = 30,
    ) -> TDocMetadata | None:
        """Fetch TDoc metadata by TDoc ID.

        Document list source does not support individual TDoc lookups.
        Use fetch_by_meeting() instead.

        Args:
            tdoc_id: TDoc identifier (e.g., "S4-251364")
            db_file: Optional path to database for meeting resolution (unused)
            timeout: Request timeout in seconds

        Returns:
            None (not supported by this source)
        """
        msg = f"Document list source does not support individual TDoc lookups for {tdoc_id}"
        raise NotImplementedError(msg)

    def fetch_by_meeting(
        self,
        meeting_id: int,
        *,
        timeout: int = 30,
    ) -> list[TDocMetadata]:
        """Fetch all TDoc metadata for a meeting via document list.

        Args:
            meeting_id: 3GPP meeting identifier
            timeout: Request timeout in seconds

        Returns:
            List of TDocMetadata for the meeting
        """
        try:
            tdocs = fetch_meeting_document_list(
                meeting_id=meeting_id,
                http_config=self.config.http_config,
                http_cache_file=self.config.http_cache_file,
                timeout=timeout,
            )
            _logger.info(f"Fetched {len(tdocs)} TDocs from document list for meeting {meeting_id}")
            return tdocs

        except DocumentListError as exc:
            _logger.warning("Document list fetch failed for meeting %s: %s", meeting_id, exc)
            return []
        except (OSError, RuntimeError, ValueError) as exc:
            _logger.exception("Unexpected error fetching document list for meeting %s: %s", meeting_id, exc)
            return []

    @property
    def source_name(self) -> str:
        """Return the name of this source for logging."""
        return "DocumentList"

    @property
    def requires_authentication(self) -> bool:
        """Return whether this source requires authentication."""
        return False


def fetch_meeting_document_list(
    meeting_id: int,
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    files_url: str | None = None,
    save_doclist_to: Path | None = None,
) -> list[TDocMetadata]:
    """Fetch all TDoc metadata for a meeting via document list Excel file.

    Args:
        meeting_id: 3GPP meeting identifier
        timeout: Request timeout in seconds
        http_config: Optional HTTP configuration from ThreeGPPConfig
        http_cache_file: Optional explicit path to the HTTP cache database
        files_url: Optional HTTP directory containing meeting documents (for URL construction)
        save_doclist_to: Optional path to save the Excel document list file for inspection

    Returns:
        List of TDocMetadata instances for all TDocs in the meeting

    Raises:
        DocumentListError: If document list cannot be fetched or parsed
    """
    tdocs, _work_items = fetch_meeting_document_list_with_work_items(
        meeting_id,
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        files_url=files_url,
        save_doclist_to=save_doclist_to,
    )
    return tdocs


def fetch_meeting_document_list_with_work_items(
    meeting_id: int,
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    files_url: str | None = None,
    save_doclist_to: Path | None = None,
) -> tuple[list[TDocMetadata], dict[str, list[str]]]:
    """Fetch TDoc metadata plus the work items each TDoc relates to.

    Returns:
        Tuple of (list of TDocMetadata, mapping of TDoc ID to work item IDs)

    Raises:
        DocumentListError: If document list cannot be fetched or parsed
    """
    # Construct document list URL
    doclist_url = DOCLIST_URL_TEMPLATE.format(portal_base=PORTAL_BASE_URL, meeting_id=meeting_id)
    _logger.debug("Fetching document list for meeting %s from %s", meeting_id, doclist_url)

    # Create cached session (no credentials required)
    session = create_cached_session(
        http_config=http_config,
        http_cache_file=http_cache_file,
    )

    try:
        # Download Excel file
        _logger.debug("Downloading Excel document list for meeting %s", meeting_id)
        response = session.get(doclist_url, timeout=timeout)
        response.raise_for_status()

        # Check if we got a valid Excel file
        content_type = response.headers.get("content-type", "").lower()
        if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in content_type and not response.content.startswith(b"PK"):
            # Some responses might not set content-type correctly, check file signature
            msg = f"Expected Excel file for meeting {meeting_id}, got content-type: {content_type}"
            raise DocumentListError(msg)

        # Save doclist to file if path is provided
        if save_doclist_to is not None:
            save_doclist_to.parent.mkdir(parents=True, exist_ok=True)
            save_doclist_to.write_bytes(response.content)
            _logger.debug("Saved document list to %s", save_doclist_to)

        # Parse Excel file
        _logger.debug("Parsing Excel document list for meeting %s", meeting_id)
        tdocs = parse_excel_document_list(response.content, meeting_id, files_url)
        return tdocs, _parse_work_items_safely(response.content, meeting_id)

    except DocumentListError:
        raise
    except (requests.RequestException, OSError, ValueError) as exc:
        _logger.warning("Failed to fetch document list for meeting %s: %s", meeting_id, exc)
        msg = f"Failed to fetch document list for meeting {meeting_id}: {exc}"
        raise DocumentListError(msg) from exc
    finally:
        session.close()


def _parse_work_items_safely(excel_content: bytes | None, meeting_id: int) -> dict[str, list[str]]:
    """Parse work item references without failing the document list fetch."""
    if not excel_content:
        return {}
    try:
        return parse_excel_work_items(excel_content, meeting_id)
    except DocumentListError as exc:
        _logger.warning("Could not parse work item references for meeting %s: %s", meeting_id, exc)
        return {}


def parse_excel_document_list(
    excel_content: bytes,
    meeting_id: int,
    files_url: str | None = None,
) -> list[TDocMetadata]:
    """Parse Excel document list and convert to TDocMetadata instances.

    Args:
        excel_content: Raw Excel file content
        meeting_id: Meeting ID for reference
        files_url: Optional HTTP directory containing meeting documents (for URL construction)

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

        _logger.debug(f"Found {len(df)} rows in TDoc_List sheet for meeting {meeting_id}")

        # Check if the dataframe has any recognizable TDoc ID columns
        # Look for any column that might contain TDoc IDs
        tdoc_columns_found = False
        for col in df.columns:
            col_str = str(col).lower()
            if any(keyword in col_str for keyword in ["tdoc", "contribution", "document", "id", "number"]):
                tdoc_columns_found = True
                break

        if not tdoc_columns_found:
            msg = f"No recognizable TDoc ID columns found in Excel file for meeting {meeting_id}"
            raise DocumentListError(msg)

        # Convert DataFrame rows to TDocMetadata instances
        tdoc_metadata_list = []
        for i, (_idx, row) in enumerate(df.iterrows()):
            try:
                tdoc_metadata = convert_excel_row_to_tdoc_metadata(row, meeting_id, files_url)
                if tdoc_metadata:
                    tdoc_metadata_list.append(tdoc_metadata)
                else:
                    _logger.debug(f"Skipping row {i + 1}: missing required TDoc ID")
            except (AttributeError, KeyError, TypeError, ValueError) as exc:
                _logger.warning(f"Failed to parse row {i + 1} for meeting {meeting_id}: {exc}")
                continue

        _logger.info(f"Successfully parsed {len(tdoc_metadata_list)} TDoc metadata entries for meeting {meeting_id}")
        return tdoc_metadata_list

    except (OSError, KeyError, ImportError, ValueError, pd.errors.ParserError) as exc:
        msg = f"Failed to parse Excel document list for meeting {meeting_id}: {exc}"
        raise DocumentListError(msg) from exc


def parse_excel_work_items(
    excel_content: bytes,
    meeting_id: int,
) -> dict[str, list[str]]:
    """Map TDoc IDs to the work items listed in their "Related WIs" column.

    The column holds a comma-separated list of work item IDs (e.g.
    ``"FS_ULBC, ULBC-MED"``) and is absent from older document lists.

    Args:
        excel_content: Raw Excel file content
        meeting_id: Meeting ID for reference (used in error messages)

    Returns:
        Mapping of TDoc ID to the work item IDs it relates to. TDocs without
        the column or without values are omitted.
    """
    try:
        df = pd.read_excel(
            io.BytesIO(excel_content),
            engine="calamine",
            sheet_name="TDoc_List",
        )
    except (OSError, KeyError, ImportError, ValueError, pd.errors.ParserError) as exc:
        msg = f"Failed to parse work items for meeting {meeting_id}: {exc}"
        raise DocumentListError(msg) from exc

    mapping: dict[str, list[str]] = {}
    for _idx, row in df.iterrows():
        tdoc_id = _extract_tdoc_id(row)
        if tdoc_id is None:
            continue
        wi_ids = parse_work_item_ids(_get_column_value(row, list(_RELATED_WI_COLUMNS)))
        if wi_ids:
            mapping[tdoc_id.upper()] = wi_ids

    _logger.debug("Found work item references for %d TDocs in meeting %s", len(mapping), meeting_id)
    return mapping


def parse_work_item_ids(raw: str | None) -> list[str]:
    """Split a "Related WIs" cell into normalized, de-duplicated work item IDs."""
    if not raw:
        return []
    wi_ids: list[str] = []
    for token in _WI_SEPARATORS.split(raw):
        candidate = token.strip().upper()
        if not candidate or candidate in _WI_PLACEHOLDERS or not _WI_ID_PATTERN.match(candidate):
            continue
        if candidate not in wi_ids:
            wi_ids.append(candidate)
    return wi_ids


def convert_excel_row_to_tdoc_metadata(
    row: pd.Series,
    meeting_id: int,
    files_url: str | None = None,
) -> TDocMetadata | None:
    """Convert a single Excel row to TDocMetadata.

    Args:
        row: pandas Series representing one Excel row
        meeting_id: Meeting ID for reference
        files_url: Optional HTTP directory containing meeting documents (for URL construction)

    Returns:
        TDocMetadata instance or None if conversion fails
    """
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
    agenda_item = _get_column_value(row, ["Agenda item"])
    agenda_item_desc = _get_column_value(row, ["Agenda item description"])
    status = _get_column_value(row, ["TDoc Status"])
    is_revision_of = _get_column_value(row, ["Is revision of"])
    date_created = _get_column_value(row, ["Date", "Created", "Date Created", "Submission Date", "Reservation date"])
    reservation_date = _get_column_value(row, ["Reservation date"])
    uploaded_at = _get_column_value(row, ["Uploaded"])
    spec_number = _get_column_value(row, ["Spec", "Specification"])
    release = _get_column_value(row, ["Release"])
    cr_number = _get_column_value(row, ["CR", "CR number"])
    cr_category = _get_column_value(row, ["CR category", "CR cat"])

    # Generate URL from files_url if available
    # Format: files_url + "/Docs/" + tdoc_id + ".zip"
    url = _construct_tdoc_url(files_url, tdoc_id.upper()) if files_url else None

    now = datetime.now(UTC)

    try:
        # Parse agenda item number and text
        agenda_nbr, agenda_text = _parse_agenda_item(agenda_item)
        # If we have a separate description column, use it instead
        if agenda_item_desc and agenda_text == "Unknown":
            agenda_text = agenda_item_desc

        # Parse dates
        parsed_date = _parse_date(date_created)
        parsed_reservation = _parse_date(reservation_date)
        parsed_uploaded = _parse_date(uploaded_at)

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
            is_revision_of=is_revision_of,
            spec_number=_clean_cell(spec_number),
            release=_clean_cell(release),
            cr_number=_clean_cell(cr_number),
            cr_category=_clean_cell(cr_category),
            file_size=None,  # Not available in Excel
            date_created=parsed_date,
            date_retrieved=now,
            date_updated=now,
            reservation_date=parsed_reservation,
            uploaded_at=parsed_uploaded,
            validated=True,  # Direct from portal, no validation needed
            validation_failed=False,
        )

    except (TypeError, ValueError) as exc:
        _logger.warning("Failed to create TDocMetadata for %s: %s", tdoc_id, exc)
        return None


def _construct_tdoc_url(files_url: str | None, tdoc_id: str) -> str | None:
    """Construct the full TDoc URL from files_url.

    Args:
        files_url: Base HTTP directory containing meeting documents
        tdoc_id: TDoc identifier (e.g., "S4-260454")

    Returns:
        Full URL to TDoc zip file (e.g., "https://.../Docs/S4-260454.zip")
        or None if files_url is not available
    """
    if not files_url:
        return None
    base = files_url.rstrip("/")
    # ``files_url`` (portal MtgDocURL) already points at the meeting ``Docs``
    # directory, e.g. ``.../TSGS4_137-e/Docs``. Only append ``/Docs`` when it
    # is not already present, so we never produce a dead ``Docs/Docs/`` path.
    if not base.endswith("/Docs"):
        base = f"{base}/Docs"
    return f"{base}/{tdoc_id.upper()}.zip"


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
    # TDoc ID pattern: [RSC][1-6P] followed by 4-10 chars
    pattern = re.compile(r"^[RSC][1-6P].{4,10}$", re.IGNORECASE)
    return bool(pattern.match(tdoc_id.strip()))


def _get_column_value(row: pd.Series, possible_names: list[str]) -> str | None:
    """Get value from row using possible column names (case-insensitive).

    Args:
        row: pandas Series representing one Excel row
        possible_names: List of possible column names

    Returns:
        Column value or None if not found
    """
    # Build lowercase lookup for case-insensitive matching
    row_lower = {k.lower(): k for k in row.index}

    for col_name in possible_names:
        actual_col = row_lower.get(col_name.lower())
        if actual_col is not None:
            value = row[actual_col]
            if value and isinstance(value, str):
                return value.strip()
            if value is not None:
                # Handle non-string values (dates, numbers, etc.)
                return str(value).strip()
    return None


def _clean_cell(value: str | None) -> str | None:
    """Normalize an optional Excel cell to a stripped string or None."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"nan", "none", "-"}:
        return None
    return cleaned


def _parse_agenda_item(agenda_item: str | None) -> tuple[AgendaItemNumber, str]:
    """Parse agenda item into number and text components.

    Args:
        agenda_item: Agenda item string (e.g., "7.1 - Some text" or just "7.1")

    Returns:
        Tuple of (agenda_number, agenda_text)
    """
    if not agenda_item:
        return parse_agenda_item_nbr("0"), "Unknown"

    # Try to split by " - " to get number and text
    parts = agenda_item.split(" - ", 1)
    if len(parts) == 2:
        agenda_nbr_str = parts[0].strip()
        agenda_text = parts[1].strip()
    else:
        # No separator found, treat whole thing as number
        agenda_nbr_str = agenda_item.strip()
        agenda_text = "Unknown"

    agenda_nbr = parse_agenda_item_nbr(agenda_nbr_str)

    return agenda_nbr, agenda_text


def _parse_date(date_value: str | None) -> datetime | None:
    """Parse date from Excel value.

    Args:
        date_value: Date value from Excel (string or datetime)

    Returns:
        datetime object or None if parsing fails
    """
    if not date_value:
        return None

    if isinstance(date_value, datetime):
        return date_value
    if isinstance(date_value, str):
        s = date_value.strip()
        # Ordered most-specific first; covers US (m/d/Y) and ISO (Y-m-d) with
        # and without AM/PM and fractional seconds.
        formats = [
            "%m/%d/%Y %I:%M:%S %p",  # 8/18/2026 3:37:04 PM
            "%d/%m/%Y %I:%M:%S %p",
            "%Y-%m-%d %H:%M:%S.%f",  # 2026-08-18 21:57:14.217000
            "%Y-%m-%dT%H:%M:%S.%f",
            "%m/%d/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


__all__ = [
    "DocumentListError",
    "DocumentListSource",
    "convert_excel_row_to_tdoc_metadata",
    "fetch_meeting_document_list",
    "fetch_meeting_document_list_with_work_items",
    "parse_excel_document_list",
    "parse_excel_work_items",
    "parse_work_item_ids",
]
