"""Meeting database operations."""

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.oxyde_models import CrawlLogEntry, MeetingMetadata, TDocMetadata
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.models.subworking_groups import SUBTB_INDEX
from tdoc_crawler.models.working_groups import WORKING_GROUP_RECORDS, WorkingGroup
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_portal_meeting_name

_logger = get_logger(__name__)


class MeetingDatabase(DocDatabase):
    """Database operations for meeting metadata."""

    # ------------------------------------------------------------------
    # Meeting operations
    # ------------------------------------------------------------------
    async def upsert_meeting(self, metadata: MeetingMetadata) -> tuple[bool, bool]:
        """Insert or update a meeting record.

        Args:
            metadata: Meeting metadata to insert or update

        Returns:
            Tuple of (created, changed) booleans
        """
        record = self._prepare_meeting(metadata)
        existing = await self._get_meeting(record.meeting_id)
        now = utc_now()

        if existing is None:
            created = MeetingMetadata(
                meeting_id=record.meeting_id,
                tbid=record.tbid,
                subtb=record.subtb,
                short_name=record.short_name,
                title=record.title,
                start_date=record.start_date,
                end_date=record.end_date,
                location=record.location,
                files_url=record.files_url,
                portal_url=record.portal_url,
                tdoc_count=record.tdoc_count,
                last_synced=record.last_synced or now,
                created_at=now,
                updated_at=now,
            )
            await MeetingMetadata.objects.create(instance=created)
            return True, False

        created_at = record.created_at or existing.created_at
        changed = self._meeting_changed(existing, record)
        updated = MeetingMetadata(
            meeting_id=record.meeting_id,
            tbid=record.tbid,
            subtb=record.subtb,
            short_name=record.short_name,
            title=record.title,
            start_date=record.start_date,
            end_date=record.end_date,
            location=record.location,
            files_url=record.files_url,
            portal_url=record.portal_url,
            tdoc_count=record.tdoc_count,
            last_synced=record.last_synced or existing.last_synced,
            created_at=created_at,
            updated_at=now,
        )
        await updated.save()
        return False, changed

    async def bulk_upsert_meetings(
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
            created, changed = await self.upsert_meeting(meeting)
            if created:
                inserted += 1
            elif changed:
                updated += 1
            if progress_callback:
                progress_callback(float(index), total)
        return inserted, updated

    async def get_existing_meeting_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[int]:
        """Get set of existing meeting IDs, optionally filtered by working group.

        Args:
            working_groups: Optional list of working groups to filter by

        Returns:
            Set of meeting IDs
        """
        if not working_groups:
            meetings = await self._table_rows(MeetingMetadata)
            return {meeting.meeting_id for meeting in meetings}

        allowed_tbids = [wg.tbid for wg in working_groups]
        meetings = await MeetingMetadata.objects.filter(tbid__in=allowed_tbids).all()
        return {meeting.meeting_id for meeting in meetings}

    async def resolve_meeting_id(self, meeting_name: str) -> int | None:
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
        all_meetings = await self.query_meetings(config)

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
    async def get_statistics(self) -> dict[str, object]:
        """Get database statistics.

        Uses SQL aggregation for counts. ``by_working_group`` still needs
        tdoc + meeting data joined in-memory due to cross-table grouping.

        Returns:
            Dictionary with various statistics
        """
        tdocs = await self._table_rows(TDocMetadata)
        meetings = await self._meeting_map()

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

        crawl_entries = await CrawlLogEntry.objects.order_by("-start_time").limit(10).all()
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
            for entry in crawl_entries
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

    @staticmethod
    async def query_meetings(config: MeetingQueryConfig) -> list[MeetingMetadata]:
        """Query meetings with filtering and sorting.

        Pushes working_group, start_date, end_date, and files_url filters
        to SQL WHERE via Oxyde ORM. Subgroup filters remain in-memory due
        to cross-table lookup requirements.

        Args:
            config: Query configuration with filters and options

        Returns:
            List of matching meeting metadata
        """
        qs = MeetingMetadata.objects

        if config.working_groups:
            allowed_tbids = [wg.tbid for wg in config.working_groups]
            qs = qs.filter(tbid__in=allowed_tbids)

        if config.start_date is not None:
            qs = qs.filter(start_date__gte=config.start_date)

        if config.end_date is not None:
            qs = qs.filter(end_date__lte=config.end_date)

        if not config.include_without_files:
            qs = qs.exclude(files_url="")

        meetings = await qs.all()

        if config.subgroups:
            allowed_subgroups = {value.strip().upper() for value in config.subgroups}
            meetings = _filter_by_subgroup(meetings, allowed_subgroups)

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

    async def _meeting_map(self) -> dict[int, MeetingMetadata]:
        """Get mapping of meeting ID to meeting metadata."""
        meetings = await self._table_rows(MeetingMetadata)
        return {meeting.meeting_id: meeting for meeting in meetings}

    @staticmethod
    async def _get_meeting(meeting_id: int) -> MeetingMetadata | None:
        """Get a meeting by ID."""
        return await MeetingMetadata.objects.filter(meeting_id=meeting_id).first()

    @staticmethod
    def _apply_meeting_filters(
        meetings: list[MeetingMetadata],
        config: MeetingQueryConfig,
    ) -> list[MeetingMetadata]:
        """Apply configured filters to a meeting list."""
        if config.working_groups:
            allowed = {wg.tbid for wg in config.working_groups}
            meetings = _filter_by_working_group(meetings, allowed)

        if config.subgroups:
            allowed_subgroups = {value.strip().upper() for value in config.subgroups}
            meetings = _filter_by_subgroup(meetings, allowed_subgroups)

        if not config.include_without_files:
            meetings = _filter_with_files(meetings)

        if config.start_date is not None:
            meetings = _filter_by_start_date(meetings, config.start_date)
        if config.end_date is not None:
            meetings = _filter_by_end_date(meetings, config.end_date)

        return meetings

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


def _filter_by_working_group(meetings: list[MeetingMetadata], allowed_tbids: set[int]) -> list[MeetingMetadata]:
    """Filter meetings by allowed TBID set."""
    return [m for m in meetings if m.tbid in allowed_tbids]


def _filter_by_subgroup(meetings: list[MeetingMetadata], allowed_codes: set[str]) -> list[MeetingMetadata]:
    """Filter meetings by subgroup codes."""
    return [m for m in meetings if m.subtb in SUBTB_INDEX and SUBTB_INDEX[m.subtb].code in allowed_codes]


def _filter_with_files(meetings: list[MeetingMetadata]) -> list[MeetingMetadata]:
    """Keep only meetings that have a files URL."""
    return [m for m in meetings if m.files_url]


def _filter_by_start_date(meetings: list[MeetingMetadata], start_date: datetime) -> list[MeetingMetadata]:
    """Keep meetings starting on or after the given date."""
    return [m for m in meetings if m.start_date and m.start_date >= start_date]


def _filter_by_end_date(meetings: list[MeetingMetadata], end_date: datetime) -> list[MeetingMetadata]:
    """Keep meetings ending on or before the given date."""
    return [m for m in meetings if m.end_date and m.end_date <= end_date]


__all__ = ["MeetingDatabase"]
