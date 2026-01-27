"""Meeting crawler for retrieving meeting metadata from 3GPP portal."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from tdoc_crawler.crawlers.constants import (DATE_PATTERN,
                                             MEETING_CODE_REGISTRY,
                                             MEETINGS_BASE_URL,
                                             PORTAL_BASE_URL)
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.models import (CrawlLimits, MeetingCrawlConfig,
                                 MeetingMetadata, WorkingGroup)

logger = logging.getLogger(__name__)


def normalize_working_group_alias(alias: str) -> str:
    """Normalize working group aliases to canonical names.

    Supports: RP→RAN, SP→SA, CP→CT, and their reverse mappings.
    """
    alias_upper = alias.strip().upper()
    # Plenary aliases
    if alias_upper in ("RP", "RAN PLENARY"):
        return "RAN"
    if alias_upper in ("SP", "SA PLENARY"):
        return "SA"
    if alias_upper in ("CP", "CT PLENARY"):
        return "CT"
    # Standard working groups
    if alias_upper in ("RAN", "SA", "CT"):
        return alias_upper
    # If not recognized, return as-is (will be validated later)
    return alias_upper


def normalize_subgroup_alias(alias: str) -> list[str]:
    """Normalize subgroup aliases to canonical names.

    Returns a list of possible matching subgroup names.
    Supports:
    - Short codes: S4, R1, C3
    - Full names: SA4, RAN1, CT3
    - Plenary codes: RP, SP, CP
    - Full plenary names: RAN PLENARY, SA PLENARY, CT PLENARY
    """
    alias_upper = alias.strip().upper()
    matches: list[str] = []

    # Try to normalize long form to short form (SA4 → S4, RAN1 → R1, CT3 → C3)
    normalized_alias = alias_upper
    if alias_upper.startswith("SA") and len(alias_upper) > 2:
        # SA4 → S4, SA1 → S1, etc.
        normalized_alias = "S" + alias_upper[2:]
    elif alias_upper.startswith("RAN") and len(alias_upper) > 3:
        # RAN1 → R1, RAN2 → R2, etc.
        normalized_alias = "R" + alias_upper[3:]
    elif alias_upper.startswith("CT") and len(alias_upper) > 2:
        # CT1 → C1, CT2 → C2, etc.
        normalized_alias = "C" + alias_upper[2:]

    # Check all registries for matches
    for _working_group, codes in MEETING_CODE_REGISTRY.items():
        for code, subgroup in codes:
            # Check if normalized alias matches the code
            if code.upper() == normalized_alias or code.upper() == alias_upper:
                if subgroup:
                    matches.append(subgroup)
            # Check if subgroup name matches
            elif subgroup and subgroup.upper() == alias_upper:
                matches.append(subgroup)

    # If no matches found, return the original alias (might be exact name)
    if not matches:
        matches.append(alias_upper)

    return matches


@dataclass(slots=True, frozen=True)
class MeetingCrawlResult:
    """Summary of a meeting crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


class MeetingCrawler:
    """Crawler fetching meeting metadata from the 3GPP portal."""

    def __init__(self, database: TDocDatabase) -> None:
        self.database = database

    def crawl(self, config: MeetingCrawlConfig, progress_callback: Callable[[float, float], None] | None = None) -> MeetingCrawlResult:
        errors: list[str] = []
        meetings: list[MeetingMetadata] = []

        working_groups = self._limit_working_groups(config.working_groups, config.limits)
        existing_ids: set[int] = set()
        if config.incremental:
            existing_ids = self.database.get_existing_meeting_ids(working_groups)
        session = create_cached_session(
            cache_dir=config.cache_dir,
            ttl=config.http_cache.ttl,
            refresh_ttl_on_access=config.http_cache.refresh_ttl_on_access,
            max_retries=config.max_retries,
        )
        session.headers["User-Agent"] = "tdoc-crawler/0.0.1"
        if config.credentials is not None:
            session.auth = (config.credentials.username, config.credentials.password)

        try:
            for working_group in working_groups:
                for code, subgroup in MEETING_CODE_REGISTRY.get(working_group.value, []):
                    # Skip subgroup if subgroups filter is set and this subgroup is not in the list
                    if config.subgroups and subgroup not in config.subgroups:
                        continue
                    url = MEETINGS_BASE_URL.format(code=code)
                    try:
                        response = session.get(url, timeout=config.timeout)
                        response.raise_for_status()
                    except Exception as exc:
                        message = f"Meeting crawl failed for {code}: {exc}"
                        logger.warning(message)
                        errors.append(message)
                        continue
                    parsed_meetings = self._parse_meeting_page(response.text, working_group, subgroup)
                    for meeting in parsed_meetings:
                        if config.incremental and meeting.meeting_id in existing_ids:
                            continue
                        meetings.append(meeting)
        finally:
            session.close()

        filtered = self._apply_limits(meetings, config.limits)
        inserted = 0
        updated = 0
        if filtered:
            # Pass progress callback to bulk_upsert_meetings to update after each DB operation
            inserted, updated = self.database.bulk_upsert_meetings(filtered, progress_callback=progress_callback)

        return MeetingCrawlResult(
            processed=len(filtered),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _limit_working_groups(self, working_groups: list[WorkingGroup], limits: CrawlLimits) -> list[WorkingGroup]:
        if limits.limit_wgs is None or limits.limit_wgs == 0:
            return working_groups
        limit = limits.limit_wgs
        return working_groups[:limit] if limit > 0 else working_groups[limit:]

    def _parse_meeting_page(
        self,
        html: str,
        working_group: WorkingGroup,
        subgroup: str | None,
    ) -> list[MeetingMetadata]:
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
                meetings.append(self._parse_meeting_row(cells, working_group, subgroup))
            except ValueError as exc:
                logger.debug("Skipping meeting row: %s", exc)
        return meetings

    def _parse_meeting_row(
        self,
        cells: list[Tag],
        working_group: WorkingGroup,
        subgroup: str | None,
    ) -> MeetingMetadata:
        short_name, portal_url, meeting_id = self._extract_meeting_reference(cells[0])
        title = cells[1].get_text(strip=True) if len(cells) > 1 else None

        start_date_text = cells[3].get_text(" ", strip=True) if len(cells) >= 4 else ""
        end_date_text = cells[4].get_text(" ", strip=True) if len(cells) >= 5 else start_date_text

        start_date = self._parse_single_date(start_date_text)
        end_date = self._parse_single_date(end_date_text)

        location = cells[2].get_text(" ", strip=True) if len(cells) > 2 else "TBC"
        files_url = self._extract_first_link(cells[-3])

        # Get tbid from working group, subtb from database lookup if subgroup is available
        tbid = working_group.tbid
        subtb: int | None = None
        if subgroup:
            subgroup_data = self.database.get_subgroup_by_code(subgroup)
            if subgroup_data:
                subtb = subgroup_data["subtb"]

        return MeetingMetadata(
            meeting_id=meeting_id,
            tbid=tbid,
            subtb=subtb,
            working_group=working_group,
            subgroup=subgroup,
            short_name=short_name,
            title=title or None,
            start_date=start_date,
            end_date=end_date,
            location=location or None,
            files_url=files_url,
            portal_url=portal_url,
        )

    def _extract_meeting_reference(self, cell: Tag) -> tuple[str, str | None, int]:
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

    def _extract_first_link(self, cell: Tag) -> str | None:
        link = cell.find("a")
        if link is None:
            return None
        raw_href = link.get("href")
        if raw_href is None:
            return None
        href = str(raw_href).replace("\\", "/").replace("//", "/")
        return href if href.startswith("http") else urljoin("https://www.3gpp.org", href)

    def _parse_dates(self, text: str) -> tuple[date | None, date | None]:
        """Parse start and end dates from text containing one or more dates.

        Handles various Unicode dash/hyphen characters by normalizing to ASCII.
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

    def _parse_single_date(self, text: str) -> date | None:
        """Parse a single date from text in YYYY-MM-DD format.

        Handles various Unicode dash/hyphen characters (U+002D, U+2010-U+2015)
        by normalizing them to ASCII hyphen-minus before parsing.
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

    def _apply_limits(self, meetings: list[MeetingMetadata], limits: CrawlLimits) -> list[MeetingMetadata]:
        if not meetings:
            return []
        filtered = list(meetings)
        filtered = self._limit_meetings_per_wg(filtered, limits.limit_meetings_per_wg)
        filtered = self._limit_meetings(filtered, limits.limit_meetings)
        return filtered

    def _limit_meetings_per_wg(
        self,
        meetings: list[MeetingMetadata],
        limit: int | None,
    ) -> list[MeetingMetadata]:
        if limit is None or limit == 0:
            return meetings
        order: dict[WorkingGroup, list[int]] = defaultdict(list)
        for meeting in meetings:
            sequence = order[meeting.working_group]
            if meeting.meeting_id not in sequence:
                sequence.append(meeting.meeting_id)
        allowed_ids: dict[WorkingGroup, set[int]] = {}
        for working_group, sequence in order.items():
            selected = sequence[:limit] if limit > 0 else sequence[limit:]
            allowed_ids[working_group] = set(selected)
        return [meeting for meeting in meetings if meeting.meeting_id in allowed_ids.get(meeting.working_group, {meeting.meeting_id})]

    def _limit_meetings(self, meetings: list[MeetingMetadata], limit: int | None) -> list[MeetingMetadata]:
        if limit is None or limit == 0:
            return meetings
        sequence: list[int] = []
        for meeting in meetings:
            if meeting.meeting_id not in sequence:
                sequence.append(meeting.meeting_id)
        allowed = set(sequence[:limit]) if limit > 0 else set(sequence[limit:])
        return [meeting for meeting in meetings if meeting.meeting_id in allowed]


__all__ = [
    "MEETING_CODE_REGISTRY",
    "MeetingCrawlResult",
    "MeetingCrawler",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
]
