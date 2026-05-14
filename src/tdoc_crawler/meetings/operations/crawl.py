"""Meeting crawler for retrieving meeting metadata from 3GPP portal REST API."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingCrawlConfig
from tdoc_crawler.meetings.sources.portal import fetch_meetings
from tdoc_crawler.models.working_groups import WorkingGroup

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class MeetingCrawlResult:
    """Summary of a meeting crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


class MeetingCrawler:
    """Crawler fetching meeting metadata from the 3GPP portal REST API."""

    def __init__(self, database: MeetingDatabase) -> None:
        if not isinstance(database, MeetingDatabase):
            msg = f"Expected MeetingDatabase, got {type(database)}"
            raise TypeError(msg)
        self.database = database

    async def crawl(
        self,
        config: MeetingCrawlConfig,
        progress_callback: Callable[[float, float], None] | None = None,
    ) -> MeetingCrawlResult:
        """Crawl meeting metadata from the portal REST API.

        Args:
            config: Configuration for crawl operation.
            progress_callback: Optional callback for progress updates.

        Returns:
            Summary of crawl results.
        """
        errors: list[str] = []

        # Determine date range from config
        start_date = config.start_date
        end_date = config.end_date

        # Build subgroup list for API filter
        subgroups: list[str] | None = None
        if config.subgroups:
            subgroups = list(config.subgroups)
        elif config.working_groups:
            # Convert WorkingGroup enum values to subgroup codes
            codes: set[str] = set()
            for wg in config.working_groups:
                if wg == WorkingGroup.RAN:
                    codes.add("RP")
                elif wg == WorkingGroup.SA:
                    codes.add("SP")
                elif wg == WorkingGroup.CT:
                    codes.add("CP")
                else:
                    codes.add(wg.value)
            subgroups = sorted(codes)

        if progress_callback:
            progress_callback(0, 0)

        try:
            meetings = fetch_meetings(
                subgroups=subgroups,
                start_date=start_date,
                end_date=end_date,
                timeout=config.timeout,
            )
        except Exception as exc:
            msg = f"Portal meetings API failed: {exc}"
            logger.exception(msg)
            errors.append(msg)
            return MeetingCrawlResult(processed=0, inserted=0, updated=0, errors=errors)

        if progress_callback:
            progress_callback(len(meetings), len(meetings))

        # Apply incremental filter
        if config.incremental and meetings:
            existing_ids = await self.database.get_existing_meeting_ids(config.working_groups)
            meetings = [m for m in meetings if m.meeting_id not in existing_ids]

        # Apply meeting count limits
        meetings = self._apply_limits(meetings, config.limit_meetings, config.limit_meetings_per_subwg)

        inserted = 0
        updated = 0
        if meetings:
            inserted, updated = await self.database.bulk_upsert_meetings(
                meetings,
                progress_callback=progress_callback,
            )

        return MeetingCrawlResult(
            processed=len(meetings),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    @staticmethod
    def _apply_limits(
        meetings: list[MeetingMetadata],
        limit_meetings: int | None,
        limit_meetings_per_subwg: int | None,
    ) -> list[MeetingMetadata]:
        """Apply all meeting limits from crawl configuration."""
        if not meetings:
            return []
        filtered = list(meetings)
        filtered = MeetingCrawler._limit_meetings_per_subwg(filtered, limit_meetings_per_subwg)
        return MeetingCrawler._limit_meetings(filtered, limit_meetings)

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
        return [m for m in meetings if m.meeting_id in allowed_ids.get(m.subtb or m.tbid, {m.meeting_id})]

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
        return [m for m in meetings if m.meeting_id in allowed]


__all__ = [
    "MeetingCrawlResult",
    "MeetingCrawler",
]
