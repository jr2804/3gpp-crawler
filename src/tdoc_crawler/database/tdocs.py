"""TDoc database operations."""

import fnmatch
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from typing import Any

from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import WorkingGroup
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_tdoc_id

_logger = get_logger(__name__)


class TDocDatabase(MeetingDatabase):
    """Unified database operations for TDocs and Meetings.

    This class provides a unified interface for both TDoc and Meeting operations
    by inheriting from MeetingDatabase. This maintains backward compatibility
    with code that expects a single database interface.
    """

    # ------------------------------------------------------------------
    # TDoc operations
    # ------------------------------------------------------------------
    async def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        """Insert or update a TDoc record.

        If ``tbid`` is not set on the metadata, resolves it from the
        associated meeting record.

        Args:
            metadata: TDoc metadata to insert or update

        Returns:
            Tuple of (created, changed) booleans
        """
        record = self._prepare_tdoc(metadata)
        if getattr(record, "tbid", None) is None:
            record = await self._resolve_tbid(record)
        existing = await self._get_tdoc(record.tdoc_id)
        now = utc_now()

        if existing is None:
            created_record = self._clone_tdoc(
                record,
                {
                    "date_updated": now,
                    "date_created": record.date_created or record.date_retrieved,
                },
            )
            await TDocMetadata.objects.create(instance=created_record)
            return True, False

        if record.date_created is None and existing.date_created is not None:
            record = self._clone_tdoc(record, {"date_created": existing.date_created})

        changed = self._tdoc_changed(existing, record)
        updated_record = self._clone_tdoc(record, {"date_updated": now})
        await updated_record.save()
        return False, changed

    async def bulk_upsert_tdocs(
        self,
        tdocs: Iterable[TDocMetadata],
        progress_callback: Callable[[float, float], None] | None = None,
    ) -> tuple[int, int]:
        """Bulk upsert TDocs with optional progress callback.

        Splits records into new vs existing, then uses ``bulk_create`` for
        inserts and ``bulk_update`` for updates instead of one-by-one queries.

        Args:
            tdocs: Iterable of TDoc metadata to upsert
            progress_callback: Optional callback to call after each batch.
                Takes (completed, total) as float parameters.

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        tdocs_list = list(tdocs)
        if not tdocs_list:
            return 0, 0

        total = float(len(tdocs_list))

        prepared: list[TDocMetadata] = []
        for metadata in tdocs_list:
            record = self._prepare_tdoc(metadata)
            if getattr(record, "tbid", None) is None:
                record = await self._resolve_tbid(record)
            prepared.append(record)

        existing_ids = set()
        for record in prepared:
            existing = await self._get_tdoc(record.tdoc_id)
            if existing is not None:
                existing_ids.add(record.tdoc_id)

        now = utc_now()
        to_create: list[TDocMetadata] = []
        to_update: list[TDocMetadata] = []
        for record in prepared:
            if record.tdoc_id not in existing_ids:
                to_create.append(self._clone_tdoc(record, {"date_updated": now, "date_created": record.date_created or record.date_retrieved}))
            else:
                to_update.append(self._clone_tdoc(record, {"date_updated": now}))

        if to_create:
            await TDocMetadata.objects.bulk_create(to_create)
        if to_update:
            await TDocMetadata.objects.bulk_update(
                to_update,
                fields=[
                    "meeting_id",
                    "tbid",
                    "title",
                    "url",
                    "source",
                    "contact",
                    "tdoc_type",
                    "for_purpose",
                    "agenda_item_nbr",
                    "agenda_item_text",
                    "status",
                    "is_revision_of",
                    "file_size",
                    "date_created",
                    "date_retrieved",
                    "date_updated",
                    "validated",
                    "validation_failed",
                ],
            )

        if progress_callback:
            progress_callback(total, total)

        return len(to_create), len(to_update)

    async def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        """Query TDocs with filtering and sorting.

        Pushes tdoc_id and working_group (via denormalized tbid) filters to
        SQL WHERE via Oxyde ORM. Meeting date filters and glob pattern filters
        still require in-memory processing because they span multiple tables
        or use fnmatch.

        Args:
            config: Query configuration with filters and options

        Returns:
            List of matching TDoc metadata
        """
        qs = TDocMetadata.objects

        if config.tdoc_ids:
            lookup = [normalize_tdoc_id(value) for value in config.tdoc_ids]
            qs = qs.filter(tdoc_id__in=lookup)

        if config.working_groups:
            allowed_tbids = [wg.tbid for wg in config.working_groups]
            qs = qs.filter(tbid__in=allowed_tbids)

        records = await qs.all()

        if not records:
            return []

        need_meeting_map = config.meeting_start_date is not None or config.meeting_end_date is not None

        if need_meeting_map:
            meeting_map = {meeting.meeting_id: meeting for meeting in await self._table_rows(MeetingMetadata)}
            records = self._filter_by_meeting_dates(records, meeting_map, config.meeting_start_date, config.meeting_end_date)

        records = self._filter_by_retrieved_dates(records, config.start_date, config.end_date)

        records = self._apply_pattern_filters(records, config)

        descending = config.order.value.lower() == "desc"
        records.sort(
            key=lambda record: (
                record.date_retrieved or datetime.min.replace(tzinfo=UTC),
                record.tdoc_id,
            ),
            reverse=descending,
        )

        if config.limit is not None:
            records = records[: config.limit]

        return records

    async def get_existing_tdoc_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[str]:
        """Get set of existing TDoc IDs, optionally filtered by working group.

        Uses the denormalized ``tbid`` field on TDocMetadata to filter
        without joining the meetings table.

        Args:
            working_groups: Optional list of working groups to filter by

        Returns:
            Set of TDoc IDs
        """
        if not working_groups:
            records = await self._table_rows(TDocMetadata)
            return {record.tdoc_id for record in records}

        allowed_tbids = [wg.tbid for wg in working_groups]
        records = await TDocMetadata.objects.filter(tbid__in=allowed_tbids).all()
        return {record.tdoc_id for record in records}

    def _apply_pattern_filters(self, records: list[TDocMetadata], config: TDocQueryConfig) -> list[TDocMetadata]:
        """Apply all supported include/exclude glob filters."""
        filtered = records
        filtered = self._filter_by_pattern(filtered, config.source_pattern, lambda record: record.source, exclude=False)
        filtered = self._filter_by_pattern(filtered, config.source_pattern_exclude, lambda record: record.source, exclude=True)
        filtered = self._filter_by_pattern(filtered, config.title_pattern, lambda record: record.title, exclude=False)
        filtered = self._filter_by_pattern(filtered, config.title_pattern_exclude, lambda record: record.title, exclude=True)
        filtered = self._filter_by_pattern(filtered, config.agenda_pattern, lambda record: record.agenda_item_text, exclude=False)
        return self._filter_by_pattern(filtered, config.agenda_pattern_exclude, lambda record: record.agenda_item_text, exclude=True)

    async def _get_tdoc(self, tdoc_id: str) -> TDocMetadata | None:
        """Get a TDoc by ID."""
        return await TDocMetadata.objects.filter(tdoc_id=tdoc_id.upper()).first()

    async def _resolve_tbid(self, record: TDocMetadata) -> TDocMetadata:
        """Resolve tbid from the associated meeting and return updated record."""
        if record.meeting_id is None:
            return record
        meeting = await MeetingMetadata.objects.filter(meeting_id=record.meeting_id).first()
        if meeting is None or meeting.tbid is None:
            return record
        return self._clone_tdoc(record, {"tbid": meeting.tbid})

    @staticmethod
    def _filter_by_retrieved_dates(
        records: list[TDocMetadata],
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[TDocMetadata]:
        """Filter records by retrieval datetime bounds."""

        def _normalized_bound(value: datetime, bound: datetime) -> tuple[datetime, datetime]:
            if value.tzinfo is None and bound.tzinfo is not None:
                return value.replace(tzinfo=UTC), bound
            if value.tzinfo is not None and bound.tzinfo is None:
                return value, bound.replace(tzinfo=UTC)
            return value, bound

        filtered = records
        if start_date is not None:
            filtered = [record for record in filtered if record.date_retrieved and (nb := _normalized_bound(record.date_retrieved, start_date))[0] >= nb[1]]
        if end_date is not None:
            filtered = [record for record in filtered if record.date_retrieved and (nb := _normalized_bound(record.date_retrieved, end_date))[0] <= nb[1]]
        return filtered

    @staticmethod
    def _filter_by_meeting_dates(
        records: list[TDocMetadata],
        meeting_map: dict[int, Any],
        meeting_start_date: date | None,
        meeting_end_date: date | None,
    ) -> list[TDocMetadata]:
        """Filter records by start/end date of the related meeting."""
        filtered = records
        if meeting_start_date is not None:
            filtered = [
                record
                for record in filtered
                if (meeting := meeting_map.get(record.meeting_id or -1)) and meeting.start_date and meeting.start_date >= meeting_start_date
            ]
        if meeting_end_date is not None:
            filtered = [
                record
                for record in filtered
                if (meeting := meeting_map.get(record.meeting_id or -1)) and meeting.end_date and meeting.end_date <= meeting_end_date
            ]
        return filtered

    @staticmethod
    def _filter_by_pattern(
        records: list[TDocMetadata],
        values: list[str] | None,
        value_getter: Callable[[TDocMetadata], str | None],
        exclude: bool,
    ) -> list[TDocMetadata]:
        """Apply case-insensitive glob filter to a selected text field."""
        if not values:
            return records
        patterns = [value.lower() for value in values]
        if exclude:
            return [
                record
                for record in records
                if not value_getter(record) or not any(fnmatch.fnmatch(str(value_getter(record)).lower(), pattern) for pattern in patterns)
            ]
        return [
            record for record in records if value_getter(record) and any(fnmatch.fnmatch(str(value_getter(record)).lower(), pattern) for pattern in patterns)
        ]

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_tdoc(metadata: TDocMetadata) -> TDocMetadata:
        """Prepare TDoc metadata for insertion (set defaults)."""
        updates: dict[str, object] = {}
        if metadata.date_retrieved is None:
            updates["date_retrieved"] = utc_now()
        if updates:
            return TDocDatabase._clone_tdoc(metadata, updates)
        return metadata

    @staticmethod
    def _tdoc_changed(current: TDocMetadata, candidate: TDocMetadata) -> bool:
        """Check if TDoc metadata has changed."""
        for field in TDocMetadata.__annotations__:
            if field == "date_updated":
                continue
            if getattr(current, field, None) != getattr(candidate, field, None):
                return True
        return False

    @staticmethod
    def _clone_tdoc(metadata: TDocMetadata, updates: dict[str, object]) -> TDocMetadata:
        """Create a new TDocMetadata instance with updates applied."""
        data = {field: getattr(metadata, field, None) for field in TDocMetadata.__annotations__}
        data.update(updates)
        return TDocMetadata(**data)


__all__ = ["TDocDatabase"]
