"""Meeting database operations."""

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingMetadata, MeetingQueryConfig
from tdoc_crawler.meetings.utils import normalize_portal_meeting_name
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.models.working_groups import WORKING_GROUP_RECORDS, WorkingGroup
from tdoc_crawler.utils.misc import utc_now

_logger = get_logger(__name__)


class MeetingDatabase(DocDatabase):
    """Database operations for meeting metadata."""

    # ------------------------------------------------------------------
    # Meeting operations
    # ------------------------------------------------------------------
    def upsert_meeting(self, metadata: MeetingMetadata) -> tuple[bool, bool]:
        """Insert or update a meeting record.

        Args:
            metadata: Meeting metadata to insert or update

        Returns:
            Tuple of (created, changed) booleans
        """
        record = self._prepare_meeting(metadata)
        existing = self._get_meeting(record.meeting_id)
        now = utc_now()

        if existing is None:
            created = record.model_copy(
                update={
                    "created_at": now,
                    "updated_at": now,
                    "last_synced": record.last_synced or now,
                }
            )
            self.connection.add("meetings", created, pk="meeting_id")
            return True, False

        if record.created_at is None:
            record = record.model_copy(update={"created_at": existing.created_at})

        changed = self._meeting_changed(existing, record)
        updated = record.model_copy(
            update={
                "last_synced": record.last_synced or existing.last_synced,
                "updated_at": now,
            }
        )
        self.connection.add("meetings", updated, pk="meeting_id")
        return False, changed

    def bulk_upsert_meetings(
        self,
        meetings: Iterable[MeetingMetadata],
        progress_callback: Callable[[float, float], None] | None = None,
    ) -> tuple[int, int]:
        """Bulk upsert meetings with optional progress callback.

        Args:
            meetings: Iterable of meeting metadata to upsert
            progress_callback: Optional callback to call after each meeting is processed.
                Takes (completed, total) as float parameters.

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        meetings_list = list(meetings)
        total = float(len(meetings_list))

        inserted = 0
        updated = 0
        for index, meeting in enumerate(meetings_list, start=1):
            created, changed = self.upsert_meeting(meeting)
            if created:
                inserted += 1
            elif changed:
                updated += 1
            if progress_callback:
                progress_callback(float(index), total)
        return inserted, updated

    def query_meetings(self, config: MeetingQueryConfig) -> list[MeetingMetadata]:
        """Query meetings with filtering and sorting.

        Args:
            config: Query configuration with filters and options

        Returns:
            List of matching meeting metadata
        """
        meetings = self._table_rows("meetings")

        if config.working_groups:
            allowed = {wg.tbid for wg in config.working_groups}
            meetings = [meeting for meeting in meetings if meeting.tbid in allowed]

        if config.subgroups:
            allowed_subgroups = {value.strip().upper() for value in config.subgroups}
            meetings = [meeting for meeting in meetings if meeting.subtb in SUBTB_INDEX and SUBTB_INDEX[meeting.subtb].code in allowed_subgroups]

        if not config.include_without_files:
            meetings = [meeting for meeting in meetings if meeting.files_url]

        # Date range filters
        if config.start_date is not None:
            meetings = [meeting for meeting in meetings if meeting.start_date and meeting.start_date >= config.start_date]
        if config.end_date is not None:
            meetings = [meeting for meeting in meetings if meeting.end_date and meeting.end_date <= config.end_date]

        descending = config.order.value.lower() == "desc"
        meetings.sort(
            key=lambda meeting: (
                meeting.start_date or datetime.min.date(),
                meeting.meeting_id,
            ),
            reverse=descending,
        )

        if config.limit is not None:
            meetings = meetings[: config.limit]

        return meetings

    def get_existing_meeting_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[int]:
        """Get set of existing meeting IDs, optionally filtered by working group.

        Args:
            working_groups: Optional list of working groups to filter by

        Returns:
            Set of meeting IDs
        """
        meetings = self._table_rows("meetings")
        if not working_groups:
            return {meeting.meeting_id for meeting in meetings}

        allowed = {wg.tbid for wg in working_groups}
        return {meeting.meeting_id for meeting in meetings if meeting.tbid in allowed}

    def resolve_meeting_id(self, meeting_name: str) -> int | None:
        """Resolve meeting name to meeting_id from database.

        Uses fuzzy matching to handle variations in meeting names:
        - Exact match (case-insensitive)
        - Normalized name match
        - Prefix/suffix matching for variations like "SA4-e" vs "3GPPSA4-e"

        Args:
            meeting_name: Meeting identifier (e.g., "SA4#133-e" or "S4-133-e")

        Returns:
            Meeting ID if found, None otherwise
        """
        config = MeetingQueryConfig(
            working_groups=None,
            subgroups=None,
            limit=None,
            order=SortOrder.DESC,
            include_without_files=True,
        )
        all_meetings = self.query_meetings(config)

        def _match_name(candidate: str, cached: str | None) -> bool:
            """Check if candidate matches cached name via fuzzy matching."""
            if not cached:
                return False
            candidate_lower = candidate.lower()
            cached_lower = cached.lower()

            if candidate_lower == cached_lower:
                return True
            return (
                cached_lower.startswith(candidate_lower)
                or cached_lower.endswith(candidate_lower)
                or candidate_lower.startswith(cached_lower)
                or candidate_lower.endswith(cached_lower)
            )

        normalized = normalize_portal_meeting_name(meeting_name)

        candidates = [meeting_name]
        if normalized != meeting_name:
            candidates.append(normalized)

        for candidate in candidates:
            for meeting in all_meetings:
                if _match_name(candidate, meeting.short_name):
                    return meeting.meeting_id

        return None

    # ------------------------------------------------------------------
    # Crawl logging and statistics
    # ------------------------------------------------------------------
    def get_statistics(self) -> dict[str, object]:
        """Get database statistics.

        Returns:
            Dictionary with various statistics
        """
        tdocs = self._table_rows("tdocs")
        meetings = self._meeting_map()
        crawl_entries = self._table_rows("crawl_log")

        by_working_group: dict[str, int] = defaultdict(int)
        tbid_to_code = {working_group.tbid: working_group.value for working_group in WorkingGroup}
        for record in tdocs:
            meeting = meetings.get(record.meeting_id or -1)
            if meeting is None:
                continue
            code = tbid_to_code.get(meeting.tbid)
            if code is None:
                _logger.debug("Unknown tbid in meeting %s: %s", meeting.meeting_id, meeting.tbid)
                continue
            by_working_group[code] += 1

        recent_crawls = [
            {
                "crawl_type": entry.crawl_type,
                "start_time": entry.start_time.isoformat(),
                "end_time": entry.end_time.isoformat() if entry.end_time else None,
                "working_groups": ",".join(entry.working_groups),
                "items_added": entry.items_added,
                "items_updated": entry.items_updated,
                "errors_count": entry.errors_count,
                "status": entry.status,
            }
            for entry in sorted(crawl_entries, key=lambda entry: entry.start_time, reverse=True)[:10]
        ]

        return {
            "total_tdocs": len(tdocs),
            "validated_tdocs": sum(1 for record in tdocs if record.validated),
            "invalid_tdocs": sum(1 for record in tdocs if record.validation_failed),
            "total_meetings": len(meetings),
            "total_working_groups": len(WORKING_GROUP_RECORDS),
            "by_working_group": dict(by_working_group),
            "recent_crawls": recent_crawls,
        }

    def _meeting_map(self) -> dict[int, MeetingMetadata]:
        """Get mapping of meeting ID to meeting metadata."""
        return {meeting.meeting_id: meeting for meeting in self._table_rows("meetings")}

    def _get_meeting(self, meeting_id: int) -> MeetingMetadata | None:
        """Get a meeting by ID."""
        try:
            return self.connection.model_from_table("meetings", str(meeting_id))
        except KeyError:
            return None

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_meeting(metadata: MeetingMetadata) -> MeetingMetadata:
        """Prepare meeting metadata for insertion (set defaults)."""
        return metadata

    @staticmethod
    def _meeting_changed(current: MeetingMetadata, candidate: MeetingMetadata) -> bool:
        """Check if meeting metadata has changed."""
        for field in MeetingMetadata.model_fields:
            if field in {"updated_at", "last_synced", "tdoc_count"}:
                continue
            if getattr(current, field) != getattr(candidate, field):
                return True
        return False


__all__ = ["MeetingDatabase"]
