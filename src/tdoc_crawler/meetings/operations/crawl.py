"""Meeting crawler for retrieving meeting metadata from 3GPP portal."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tdoc_crawler.constants.urls import MEETINGS_BASE_URL
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingCrawlConfig, MeetingMetadata
from tdoc_crawler.models.subworking_groups import (
    CODE_INDEX,
    SUBWORKING_GROUP_RECORDS,
    SubWorkingGroupRecord,
)
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

    async def crawl(
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

        working_groups = self._limit_working_groups(config.working_groups, config.limit_subwgs)
        existing_ids: set[int] = set()
        if config.incremental:
            existing_ids = await self.database.get_existing_meeting_ids(working_groups)
        credentials = resolve_credentials(None, None)
        session = create_cached_session(http_config=config.http_config)
        if credentials is not None:
            session.auth = (credentials.username, credentials.password)

        try:
            for working_group in working_groups:
                meetings.extend(
                    self._crawl_working_group(
                        session=session,
                        working_group=working_group,
                        config=config,
                        existing_ids=existing_ids,
                        errors=errors,
                    )
                )
        finally:
            session.close()

        filtered = self._apply_limits(meetings, config.limit_meetings, config.limit_meetings_per_subwg)
        inserted = 0
        updated = 0
        if filtered:
            # Pass progress callback to bulk_upsert_meetings to update after each DB operation
            inserted, updated = await self.database.bulk_upsert_meetings(
                filtered,
                progress_callback=progress_callback,
            )

        return MeetingCrawlResult(
            processed=len(filtered),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _crawl_working_group(
        self,
        session: Any,
        working_group: WorkingGroup,
        config: MeetingCrawlConfig,
        existing_ids: set[int],
        errors: list[str],
    ) -> list[MeetingMetadata]:
        """Crawl and parse meeting metadata for one working group."""
        meetings: list[MeetingMetadata] = []
        records = [record for record in SUBWORKING_GROUP_RECORDS if record.tbid == working_group.tbid and self._record_is_in_scope(record, config)]
        for record in records:
            html_text = self._fetch_meeting_page_text(session, record, config.timeout, errors)
            if html_text is None:
                continue
            parsed_meetings = parse_meeting_page(
                html_text,
                working_group,
                record.code,
                get_subtb=self._get_subtb,
            )
            for meeting in parsed_meetings:
                if self._include_meeting(meeting, config, existing_ids):
                    meetings.append(meeting)
        return meetings

    def _apply_limits(
        self,
        meetings: list[MeetingMetadata],
        limit_meetings: int | None,
        limit_meetings_per_subwg: int | None,
    ) -> list[MeetingMetadata]:
        """Apply all meeting limits from crawl configuration."""
        if not meetings:
            return []
        filtered = list(meetings)
        filtered = self._limit_meetings_per_subwg(filtered, limit_meetings_per_subwg)
        filtered = self._limit_meetings(filtered, limit_meetings)
        return filtered

    @staticmethod
    def _get_subtb(subgroup_code: str) -> int | None:
        """Resolve subgroup code to subtb via lookup index."""
        record = CODE_INDEX.get(subgroup_code.upper())
        return record.subtb if record else None

    @staticmethod
    def _record_is_in_scope(record: SubWorkingGroupRecord, config: MeetingCrawlConfig) -> bool:
        """Check whether subgroup record should be crawled for the current config."""
        return not config.subgroups or record.code in config.subgroups

    @staticmethod
    def _include_meeting(meeting: MeetingMetadata, config: MeetingCrawlConfig, existing_ids: set[int]) -> bool:
        """Apply incremental and files-url filters before persisting meetings."""
        if config.incremental and meeting.meeting_id in existing_ids:
            return False
        return config.include_without_files or bool(meeting.files_url)

    @staticmethod
    def _fetch_meeting_page_text(session: Any, record: SubWorkingGroupRecord, timeout: float, errors: list[str]) -> str | None:
        """Fetch meeting page HTML text for one subgroup record."""
        url = MEETINGS_BASE_URL.format(code=record.code)
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
        except Exception as exc:
            message = f"Meeting crawl failed for {record.code}: {exc}"
            logger.warning(message)
            errors.append(message)
            return None
        return response.text

    @staticmethod
    def _limit_working_groups(
        working_groups: list[WorkingGroup],
        limit_subwgs: int | None,
    ) -> list[WorkingGroup]:
        """Apply working group limits from crawl configuration."""
        if limit_subwgs is None or limit_subwgs == 0:
            return working_groups
        return working_groups[:limit_subwgs] if limit_subwgs > 0 else working_groups[limit_subwgs:]

    @staticmethod
    def _limit_meetings_per_subwg(
        meetings: list[MeetingMetadata],
        limit: int | None,
    ) -> list[MeetingMetadata]:
        """Limit number of meetings per sub-working group."""
        if limit is None or limit == 0:
            return meetings
        order: dict[int, list[int]] = defaultdict(list)
        for meeting in meetings:
            wg_id = meeting.subtb or meeting.tbid
            sequence = order[wg_id]
            if meeting.meeting_id not in sequence:
                sequence.append(meeting.meeting_id)
        allowed_ids: dict[int, set[int]] = {}
        for wg_id, sequence in order.items():
            selected = sequence[:limit] if limit > 0 else sequence[limit:]
            allowed_ids[wg_id] = set(selected)
        return [meeting for meeting in meetings if meeting.meeting_id in allowed_ids.get(meeting.subtb or meeting.tbid, {meeting.meeting_id})]

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
