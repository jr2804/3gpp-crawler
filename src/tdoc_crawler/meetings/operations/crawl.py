"""Meeting crawler for retrieving meeting metadata from 3GPP portal."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from tdoc_crawler.constants.registry import MEETING_CODE_REGISTRY
from tdoc_crawler.constants.urls import MEETINGS_BASE_URL
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingCrawlConfig, MeetingMetadata
from tdoc_crawler.models.crawl_limits import CrawlLimits
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.parsers.meetings import parse_meeting_page

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class MeetingCrawlResult:
    """Summary of a meeting crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


class MeetingCrawler:
    """Crawler fetching meeting metadata from the 3GPP portal."""

    def __init__(self, database: MeetingDatabase) -> None:

        if not isinstance(database, MeetingDatabase):
            raise TypeError(f"Expected MeetingDatabase, got {type(database)}")
        self.database = database

    def crawl(
        self,
        config: MeetingCrawlConfig,
        progress_callback: Callable[[float, float], None] | None = None,
    ) -> MeetingCrawlResult:
        """Crawl meeting metadata from 3GPP portal.

        Args:
            config: Configuration for crawl operation
            progress_callback: Optional callback for progress updates (processed, total)

        Returns:
            Summary of crawl results (processed, inserted, updated, errors)
        """
        errors: list[str] = []
        meetings: list[MeetingMetadata] = []

        working_groups = self._limit_working_groups(config.working_groups, config.limits)
        existing_ids: set[int] = set()
        if config.incremental:
            existing_ids = self.database.get_existing_meeting_ids(working_groups)
        credentials = resolve_credentials(None, None)
        session = create_cached_session(cache_manager_name=config.cache_manager_name, http_cache=config.http_cache)
        session.headers["User-Agent"] = "tdoc-crawler/0.0.1"
        if credentials is not None:
            session.auth = (credentials.username, credentials.password)

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

                    # Create callback for subtb lookup
                    def get_subtb(subgroup_code: str) -> int | None:
                        """Get subtb from subgroup code via database lookup."""
                        subgroup_data = self.database.get_subgroup_by_code(subgroup_code)
                        return subgroup_data["subtb"] if subgroup_data else None

                    parsed_meetings = parse_meeting_page(
                        response.text,
                        working_group,
                        subgroup,
                        get_subtb=get_subtb,
                    )
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
            inserted, updated = self.database.bulk_upsert_meetings(
                filtered,
                progress_callback=progress_callback,
            )

        return MeetingCrawlResult(
            processed=len(filtered),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _apply_limits(
        self,
        meetings: list[MeetingMetadata],
        limits: CrawlLimits,
    ) -> list[MeetingMetadata]:
        """Apply all meeting limits from crawl configuration."""
        if not meetings:
            return []
        filtered = list(meetings)
        filtered = self._limit_meetings_per_wg(filtered, limits.limit_meetings_per_wg)
        filtered = self._limit_meetings(filtered, limits.limit_meetings)
        return filtered

    @staticmethod
    def _limit_working_groups(
        working_groups: list[WorkingGroup],
        limits: CrawlLimits,
    ) -> list[WorkingGroup]:
        """Apply working group limits from crawl configuration."""
        if limits.limit_wgs is None or limits.limit_wgs == 0:
            return working_groups
        limit = limits.limit_wgs
        return working_groups[:limit] if limit > 0 else working_groups[limit:]

    @staticmethod
    def _limit_meetings_per_wg(
        meetings: list[MeetingMetadata],
        limit: int | None,
    ) -> list[MeetingMetadata]:
        """Limit number of meetings per working group."""
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

    @staticmethod
    def _limit_meetings(
        meetings: list[MeetingMetadata],
        limit: int | None,
    ) -> list[MeetingMetadata]:
        """Limit total number of meetings across all working groups."""
        if limit is None or limit == 0:
            return meetings
        sequence: list[int] = []
        for meeting in meetings:
            if meeting.meeting_id not in sequence:
                sequence.append(meeting.meeting_id)
        allowed = set(sequence[:limit]) if limit > 0 else set(sequence[limit:])
        return [meeting for meeting in meetings if meeting.meeting_id in allowed]


__all__ = [
    "MeetingCrawlResult",
    "MeetingCrawler",
]
