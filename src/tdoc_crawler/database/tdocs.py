"""TDoc database operations."""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models import WorkingGroup
from tdoc_crawler.tdocs.models import TDocMetadata, TDocQueryConfig
from tdoc_crawler.utils.misc import utc_now

_logger = get_logger(__name__)


class TDocDatabase(DocDatabase):
    """Unified database operations for TDocs and Meetings.

    This class provides a unified interface for both TDoc and Meeting operations
    by inheriting from DocDatabase. This maintains backward compatibility
    with code that expects a single database interface.
    """

    # ------------------------------------------------------------------
    # TDoc operations
    # ------------------------------------------------------------------
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        """Insert or update a TDoc record.

        Args:
            metadata: TDoc metadata to insert or update

        Returns:
            Tuple of (created, changed) booleans
        """
        record = self._prepare_tdoc(metadata)
        existing = self._get_tdoc(record.tdoc_id)
        now = utc_now()

        if existing is None:
            created_record = record.model_copy(
                update={
                    "date_updated": now,
                    "date_created": record.date_created or record.date_retrieved,
                }
            )
            self.connection.add("tdocs", created_record, pk="tdoc_id")
            return True, False

        if record.date_created is None and existing.date_created is not None:
            record = record.model_copy(update={"date_created": existing.date_created})

        changed = self._tdoc_changed(existing, record)
        updated_record = record.model_copy(update={"date_updated": now})
        self.connection.add("tdocs", updated_record, pk="tdoc_id")
        return False, changed

    def bulk_upsert_tdocs(
        self,
        tdocs: Iterable[TDocMetadata],
        progress_callback: Callable[[float, float], None] | None = None,
    ) -> tuple[int, int]:
        """Bulk upsert TDocs with optional progress callback.

        Args:
            tdocs: Iterable of TDoc metadata to upsert
            progress_callback: Optional callback to call after each TDoc is processed.
                Takes (completed, total) as float parameters.

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        tdocs_list = list(tdocs)
        total = float(len(tdocs_list))

        inserted = 0
        updated = 0
        for index, metadata in enumerate(tdocs_list, start=1):
            created, changed = self.upsert_tdoc(metadata)
            if created:
                inserted += 1
            elif changed:
                updated += 1
            if progress_callback:
                progress_callback(float(index), total)
        return inserted, updated

    def query_tdocs(self, config: TDocQueryConfig) -> list[TDocMetadata]:
        """Query TDocs with filtering and sorting.

        Args:
            config: Query configuration with filters and options

        Returns:
            List of matching TDoc metadata
        """
        records = self._table_rows("tdocs")
        if not records:
            return []

        meeting_db = MeetingDatabase(self.db_file)
        meeting_db._database = self._database  # Share connection
        meeting_map = meeting_db._meeting_map()

        if config.tdoc_ids:
            lookup = {value.strip().upper() for value in config.tdoc_ids}
            records = [record for record in records if record.tdoc_id in lookup]

        if config.working_groups:
            allowed_tbids = {wg.tbid for wg in config.working_groups}
            filtered: list[TDocMetadata] = []
            for record in records:
                meeting = meeting_map.get(record.meeting_id or -1)
                if meeting is None or meeting.tbid not in allowed_tbids:
                    continue
                filtered.append(record)
            records = filtered

        if config.start_date is not None:
            records = [record for record in records if record.date_retrieved and record.date_retrieved >= config.start_date]
        if config.end_date is not None:
            records = [record for record in records if record.date_retrieved and record.date_retrieved <= config.end_date]

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

    def get_existing_tdoc_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[str]:
        """Get set of existing TDoc IDs, optionally filtered by working group.

        Args:
            working_groups: Optional list of working groups to filter by

        Returns:
            Set of TDoc IDs
        """
        records = self._table_rows("tdocs")
        if not working_groups:
            return {record.tdoc_id for record in records}

        meeting_db = MeetingDatabase(self.db_file)
        meeting_db._database = self._database  # Share connection
        meeting_map = meeting_db._meeting_map()

        allowed_tbids = {wg.tbid for wg in working_groups}

        result: set[str] = set()
        for record in records:
            meeting = meeting_map.get(record.meeting_id or -1)
            if meeting is None:
                continue
            if meeting.tbid in allowed_tbids:
                result.add(record.tdoc_id)
        return result

    def get_processed_meetings(
        self,
        working_groups: Iterable[WorkingGroup] | None = None,
        subgroups: Iterable[str] | None = None,
    ) -> set[int]:
        """Get set of meeting IDs that have TDocs stored.

        Args:
            working_groups: Optional list of working groups to filter by
            subgroups: Optional list of subgroup codes to filter by

        Returns:
            Set of meeting IDs
        """
        records = self._table_rows("tdocs")

        meeting_db = MeetingDatabase(self.db_file)
        meeting_db._database = self._database  # Share connection
        meeting_map = meeting_db._meeting_map()

        allowed_tbids = {wg.tbid for wg in working_groups} if working_groups else None
        allowed_subgroups = {value.strip().upper() for value in subgroups} if subgroups else None

        processed: set[int] = set()
        for record in records:
            if record.meeting_id is None:
                continue
            meeting = meeting_map.get(record.meeting_id)
            if meeting is None:
                continue
            if allowed_tbids and meeting.tbid not in allowed_tbids:
                continue
            if allowed_subgroups and (meeting.subgroup or "").upper() not in allowed_subgroups:
                continue
            processed.add(record.meeting_id)
        return processed

    def cache_invalid_tdoc(
        self,
        tdoc_id: str,
        url: str,
        working_group: WorkingGroup,
        subgroup: str,
    ) -> None:
        """Cache an invalid TDoc (for deduplication during crawling).

        Args:
            tdoc_id: TDoc identifier
            url: TDoc URL
            working_group: Working group
            subgroup: Subgroup code
        """
        _ = (working_group, subgroup)
        if self._get_tdoc(tdoc_id) is not None:
            return

        metadata = TDocMetadata(
            tdoc_id=tdoc_id,
            url=url,
            meeting_id=0,
            title="Unknown",
            contact="Unknown",
            source="Unknown",
            tdoc_type="unknown",
            for_purpose="unknown",
            agenda_item_nbr=Decimal("0.0"),
            agenda_item_text="Unknown",
            status=None,
            meeting_name=None,
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=True,
        )
        self.connection.add("tdocs", metadata.model_copy(update={"date_updated": utc_now()}), pk="tdoc_id")

    def get_cached_invalid_tdocs(self) -> set[str]:
        """Get set of TDoc IDs marked as invalid.

        Returns:
            Set of invalid TDoc IDs
        """
        return {record.tdoc_id for record in self._table_rows("tdocs") if record.validation_failed}

    def _get_tdoc(self, tdoc_id: str) -> TDocMetadata | None:
        """Get a TDoc by ID."""
        try:
            return self.connection.model_from_table("tdocs", tdoc_id.upper())  # type: ignore[arg-type]
        except KeyError:
            return None

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
            return metadata.model_copy(update=updates)
        return metadata

    @staticmethod
    def _tdoc_changed(current: TDocMetadata, candidate: TDocMetadata) -> bool:
        """Check if TDoc metadata has changed."""
        for field in TDocMetadata.model_fields:
            if field == "date_updated":
                continue
            if getattr(current, field) != getattr(candidate, field):
                return True
        return False


__all__ = ["TDocDatabase"]
