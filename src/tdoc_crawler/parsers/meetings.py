"""Meeting HTML parser for extracting meeting metadata from 3GPP portal pages."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from tdoc_crawler.constants.patterns import DATE_PATTERN
from tdoc_crawler.constants.urls import PORTAL_BASE_URL
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingMetadata
from tdoc_crawler.models.working_groups import WorkingGroup

logger = get_logger(__name__)


class MeetingParser:
    """HTML parser for 3GPP portal meeting list pages.

    Wraps the standalone ``parse_meeting_page`` function with optional
    session injection for forward-compatibility with DI patterns.

    Args:
        session: Optional requests.Session to reuse for any HTTP operations.
            If not provided, one is created via ``create_cached_session()``
            on first use.

    Example:
        >>> parser = MeetingParser()
        >>> meetings = parser.parse(html, working_group, subgroup)
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        """Initialize MeetingParser.

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

    @staticmethod
    def parse(
        html: str,
        working_group: WorkingGroup,
        subgroup: str | None,
        get_subtb: Callable[[str], int | None] | None = None,
    ) -> list[MeetingMetadata]:
        """Parse meeting page HTML into list of MeetingMetadata.

        Args:
            html: HTML content of meeting page.
            working_group: The working group for these meetings.
            subgroup: Optional subgroup name.
            get_subtb: Optional callback to get subtb from subgroup code.

        Returns:
            List of parsed meeting metadata objects.
        """
        return parse_meeting_page(html, working_group, subgroup, get_subtb)

def parse_meeting_page(
    html: str,
    working_group: WorkingGroup,
    subgroup: str | None,
    get_subtb: Callable[[str], int | None] | None = None,
) -> list[MeetingMetadata]:
    """Parse meeting page HTML into list of MeetingMetadata.

    Args:
        html: HTML content of meeting page
        working_group: The working group for these meetings
        subgroup: Optional subgroup name
        get_subtb: Optional callback to get subtb from subgroup code

    Returns:
        List of parsed meeting metadata objects
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []
    meetings: list[MeetingMetadata] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        try:
            meeting = parse_meeting_row(cells, working_group, subgroup, get_subtb)
            meetings.append(meeting)
        except ValueError as exc:
            logger.debug("Skipping meeting row: %s", exc)
    return meetings


def parse_meeting_row(
    cells: list[Tag],
    working_group: WorkingGroup,
    subgroup: str | None,
    get_subtb: Callable[[str], int | None] | None = None,
) -> MeetingMetadata:
    """Parse a single meeting row from the table.

    Args:
        cells: Table cells from the row
        working_group: The working group for this meeting
        subgroup: Optional subgroup name
        get_subtb: Optional callback to get subtb from subgroup code

    Returns:
        Parsed meeting metadata

    Raises:
        ValueError: If required fields are missing or malformed
    """
    short_name, portal_url, meeting_id = extract_meeting_reference(cells[0])
    title = cells[1].get_text(strip=True) if len(cells) > 1 else None

    start_date_text = cells[3].get_text(" ", strip=True) if len(cells) >= 4 else ""
    end_date_text = cells[4].get_text(" ", strip=True) if len(cells) >= 5 else start_date_text

    start_date = parse_single_date(start_date_text)
    end_date = parse_single_date(end_date_text)

    location = cells[2].get_text(" ", strip=True) if len(cells) > 2 else "TBC"
    files_url = extract_first_link(cells[-3])

    tbid = working_group.tbid
    subtb: int | None = None
    if subgroup and get_subtb:
        subtb = get_subtb(subgroup)

    return MeetingMetadata(
        meeting_id=meeting_id,
        tbid=tbid,
        subtb=subtb,
        short_name=short_name,
        title=title or None,
        start_date=start_date,
        end_date=end_date,
        location=location or None,
        files_url=files_url,
        portal_url=portal_url,
        tdoc_count=0,
    )


def extract_meeting_reference(cell: Tag) -> tuple[str, str | None, int]:
    """Extract meeting short name, portal URL, and ID from table cell.

    Args:
        cell: Table cell containing meeting link

    Returns:
        Tuple of (short_name, portal_url, meeting_id)

    Raises:
        ValueError: If link or meeting ID is missing
    """
    short_name = cell.get_text(strip=True)
    link = cell.find("a")
    if link is None:
        raise ValueError("missing-meeting-link")
    raw_href = link.get("href")
    if raw_href is None:
        raise ValueError("missing-meeting-link")
    href = str(raw_href)
    portal_url = href if href.startswith("http") else urljoin(PORTAL_BASE_URL, href)
    match = re.search(r"MtgId=(\d+)", href)
    if match is None:
        raise ValueError("missing-meeting-id")
    meeting_id = int(match.group(1))
    return short_name, portal_url, meeting_id


def extract_first_link(cell: Tag) -> str | None:
    """Extract the first link from a table cell.

    Args:
        cell: Table cell potentially containing a link

    Returns:
        Absolute URL or None if no link found
    """
    link = cell.find("a")
    if link is None:
        return None
    raw_href = link.get("href")
    if raw_href is None:
        return None
    href = str(raw_href).replace("\\", "/").replace("//", "/")
    return href if href.startswith("http") else urljoin("https://www.3gpp.org", href)


def parse_dates(text: str) -> tuple[date | None, date | None]:
    """Parse start and end dates from text containing one or more dates.

    Handles various Unicode dash/hyphen characters by normalizing to ASCII.

    Args:
        text: Text containing dates in YYYY-MM-DD format

    Returns:
        Tuple of (start_date, end_date), both may be None
    """
    matches = DATE_PATTERN.findall(text)
    if not matches:
        return None, None
    # Normalize Unicode dashes to ASCII hyphen-minus
    start_normalized = matches[0].translate(str.maketrans("\u2010\u2011\u2012\u2013\u2014\u2015", "------"))
    start = date.fromisoformat(start_normalized)
    if len(matches) > 1:
        end_normalized = matches[-1].translate(str.maketrans("\u2010\u2011\u2012\u2013\u2014\u2015", "------"))
        end = date.fromisoformat(end_normalized)
    else:
        end = start
    return start, end


def parse_single_date(text: str) -> date | None:
    """Parse a single date from text in YYYY-MM-DD format.

    Handles various Unicode dash/hyphen characters (U+002D, U+2010-U+2015)
    by normalizing them to ASCII hyphen-minus before parsing.

    Args:
        text: Text containing a date

    Returns:
        Parsed date or None if not found
    """
    if not text:
        return None
    match = DATE_PATTERN.search(text)
    if match is None:
        return None
    # Normalize Unicode dashes to ASCII hyphen-minus for ISO format parsing
    date_str = match.group(1)
    normalized = date_str.translate(str.maketrans("\u2010\u2011\u2012\u2013\u2014\u2015", "------"))
    return date.fromisoformat(normalized)


__all__ = [
    "MeetingParser",
    "extract_first_link",
    "extract_meeting_reference",
    "parse_dates",
    "parse_meeting_page",
    "parse_meeting_row",
    "parse_single_date",
]
