"""Meeting database operations."""

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.meetings.models import MeetingMetadata, MeetingQueryConfig
from tdoc_crawler.models.crawl_log import CrawlLogEntry
from tdoc_crawler.models.subworking_groups import CODE_INDEX
from tdoc_crawler.models.working_groups import WORKING_GROUP_RECORDS, WorkingGroup
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_portal_meeting_name

_logger = logging.getLogger(__name__)


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
            allowed = {wg.value for wg in config.working_groups}
            meetings = [meeting for meeting in meetings if meeting.working_group and meeting.working_group in allowed]

        if config.subgroups:
            allowed_subgroups = {value.strip().upper() for value in config.subgroups}
            meetings = [meeting for meeting in meetings if (meeting.subgroup or "").upper() in allowed_subgroups]

        if not config.include_without_files:
            meetings = [meeting for meeting in meetings if meeting.files_url]

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

        allowed = {wg.value for wg in working_groups}
        return {meeting.meeting_id for meeting in meetings if meeting.working_group and meeting.working_group in allowed}

    def get_tdoc_count_for_meeting(self, meeting_id: int) -> int:
        """Get the number of TDocs associated with a meeting.

        Args:
            meeting_id: The meeting identifier

        Returns:
            Number of TDocs for this meeting
        """
        tdocs = self._table_rows("tdocs")
        return sum(1 for tdoc in tdocs if tdoc.meeting_id == meeting_id)

    def update_meeting_tdoc_count(self, meeting_id: int, tdoc_count: int) -> None:
        """Update the tdoc_count field for a meeting.

        Args:
            meeting_id: The meeting identifier
            tdoc_count: The new TDoc count
        """
        meeting = self._get_meeting(meeting_id)
        if meeting is None:
            return

        updated = meeting.model_copy(
            update={
                "tdoc_count": tdoc_count,
                "updated_at": utc_now(),
            }
        )
        self.connection.add("meetings", updated, pk="meeting_id")

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
            cache_dir=self.db_file.parent,
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

    def get_subgroup_by_code(self, code: str) -> dict[str, int | str] | None:
        """Get subgroup metadata by code.

        Args:
            code: Subgroup code (e.g., "S4", "R1")

        Returns:
            Dictionary with subgroup metadata or None if not found
        """
        record = CODE_INDEX.get(code.strip().upper())
        if record is None:
            return None
        return {
            "subtb": record.subtb,
            "tbid": record.tbid,
            "code": record.code,
            "name": record.name,
        }

    # ------------------------------------------------------------------
    # Crawl logging and statistics
    # ------------------------------------------------------------------
    def log_crawl_start(
        self,
        crawl_type: str,
        working_groups: Iterable[WorkingGroup] | None,
        incremental: bool,
    ) -> str:
        """Log the start of a crawl operation.

        Args:
            crawl_type: Type of crawl (e.g., "meeting", "tdoc")
            working_groups: List of working groups being crawled
            incremental: Whether this is an incremental crawl

        Returns:
            Crawl log ID
        """
        entry = CrawlLogEntry(
            crawl_type=crawl_type,
            end_time=None,
            working_groups=[wg.value for wg in working_groups or []],
            incremental=incremental,
            items_added=0,
            items_updated=0,
            errors_count=0,
            status="RUNNING",
        )
        self.connection.add("crawl_log", entry, pk="log_id")
        return entry.log_id

    def log_crawl_end(
        self,
        crawl_id: str,
        *,
        items_added: int,
        items_updated: int,
        errors_count: int,
        status: str = "COMPLETED",
    ) -> None:
        """Log the completion of a crawl operation.

        Args:
            crawl_id: Crawl log ID returned by log_crawl_start
            items_added: Number of new items added
            items_updated: Number of existing items updated
            errors_count: Number of errors encountered
            status: Final status (default: "COMPLETED")
        """
        existing = self.connection.model_from_table("crawl_log", crawl_id)
        updated = existing.model_copy(
            update={
                "end_time": utc_now(),
                "items_added": items_added,
                "items_updated": items_updated,
                "errors_count": errors_count,
                "status": status,
            }
        )
        self.connection.add("crawl_log", updated, pk="log_id")

    def get_statistics(self) -> dict[str, object]:
        """Get database statistics.

        Returns:
            Dictionary with various statistics
        """
        tdocs = self._table_rows("tdocs")
        meetings = self._meeting_map()
        crawl_entries = self._table_rows("crawl_log")

        by_working_group: dict[str, int] = defaultdict(int)
        for record in tdocs:
            meeting = meetings.get(record.meeting_id or -1)
            if meeting and meeting.working_group:
                by_working_group[meeting.working_group] += 1

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
        if metadata.working_group is None and metadata.tbid:
            for working_group in WorkingGroup:
                if working_group.tbid == metadata.tbid:
                    return metadata.model_copy(update={"working_group": working_group})
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
