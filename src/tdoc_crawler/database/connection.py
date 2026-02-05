"""Database access layer backed by pydantic_sqlite."""

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_sqlite import DataBase

from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.models import (
    CODE_INDEX,
    WORKING_GROUP_RECORDS,
    CrawlLogEntry,
    MeetingMetadata,
    MeetingQueryConfig,
    QueryConfig,
    TDocMetadata,
    WorkingGroup,
    utc_now,
)
from tdoc_crawler.models.specs import Specification, SpecificationDownload, SpecificationSourceRecord, SpecificationVersion
from tdoc_crawler.models.subworking_groups import SUBWORKING_GROUP_RECORDS

if TYPE_CHECKING:
    from tdoc_crawler.specs.query import SpecQueryFilters, SpecQueryResult


class TDocDatabase:
    """High-level facade for all database operations."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._database: DataBase | None = None

    # ------------------------------------------------------------------
    # Context manager lifecycle
    # ------------------------------------------------------------------
    def __enter__(self) -> TDocDatabase:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._database = DataBase(self.db_path)
            self._ensure_reference_data()
        except Exception as exc:
            raise DatabaseError("database-initialization-failed", detail=str(exc)) from exc
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: object | None) -> None:
        self._database = None

    # ------------------------------------------------------------------
    # Core accessors and utilities
    # ------------------------------------------------------------------
    @property
    def connection(self) -> DataBase:
        """Expose the underlying DataBase instance (read-only)."""
        if self._database is None:
            raise DatabaseError.connection_not_open()
        return self._database

    # ------------------------------------------------------------------
    # TDoc operations
    # ------------------------------------------------------------------
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
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
        # Convert to list to get total count
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
            # Call progress callback after each TDoc is processed
            if progress_callback:
                progress_callback(float(index), total)
        return inserted, updated

    def query_tdocs(self, config: QueryConfig) -> list[TDocMetadata]:
        records = self._table_rows("tdocs")
        meeting_map = self._meeting_map()

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
        records = self._table_rows("tdocs")
        if not working_groups:
            return {record.tdoc_id for record in records}

        meeting_map = self._meeting_map()
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
        records = self._table_rows("tdocs")
        meeting_map = self._meeting_map()

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
        _ = (working_group, subgroup)
        if self._get_tdoc(tdoc_id) is not None:
            return

        metadata = TDocMetadata(
            tdoc_id=tdoc_id,
            url=url,
            meeting_id=0,  # Required field, use 0 as placeholder
            title="Unknown",  # Required field
            contact="Unknown",  # Required field
            source="Unknown",  # Required field
            tdoc_type="unknown",  # Required field with default
            for_purpose="unknown",  # Required field with default
            agenda_item_nbr=Decimal("0.0"),  # Required field
            agenda_item_text="Unknown",  # Required field with default
            status=None,  # Optional field
            meeting_name=None,  # Optional field
            is_revision_of=None,  # Optional field
            file_size=None,  # Optional field
            date_created=None,  # Optional field
            validated=False,  # Required field with default
            validation_failed=True,  # Required field with default
        )
        self.connection.add("tdocs", metadata.model_copy(update={"date_updated": utc_now()}), pk="tdoc_id")

    def get_cached_invalid_tdocs(self) -> set[str]:
        return {record.tdoc_id for record in self._table_rows("tdocs") if record.validation_failed}

    # ------------------------------------------------------------------
    # Meeting operations
    # ------------------------------------------------------------------
    def upsert_meeting(self, metadata: MeetingMetadata) -> tuple[bool, bool]:
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
        # Convert to list to get total count
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
            # Call progress callback after each meeting is processed
            if progress_callback:
                progress_callback(float(index), total)
        return inserted, updated

    def query_meetings(self, config: MeetingQueryConfig) -> list[MeetingMetadata]:
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

    def get_subgroup_by_code(self, code: str) -> dict[str, int | str] | None:
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
    # Spec operations
    # ------------------------------------------------------------------
    def upsert_specification(self, specification: Specification) -> tuple[bool, bool]:
        """Upsert a specification record."""
        existing = self._get_specification(specification.spec_number)
        if existing is None:
            self.connection.add("specs", specification, pk="spec_number")
            return True, False

        changed = self._spec_changed(existing, specification)
        self.connection.add("specs", specification, pk="spec_number")
        return False, changed

    def upsert_spec_source_record(self, record: SpecificationSourceRecord) -> tuple[bool, bool]:
        """Upsert a spec source record."""
        record_id = record.record_id or f"{record.spec_number}:{record.source_name}"
        updated_record = record.model_copy(update={"record_id": record_id})
        existing = self._get_spec_source_record(record_id)
        if existing is None:
            self.connection.add("spec_source_records", updated_record, pk="record_id")
            return True, False

        changed = self._spec_source_changed(existing, updated_record)
        self.connection.add("spec_source_records", updated_record, pk="record_id")
        return False, changed

    def upsert_spec_version(self, version: SpecificationVersion) -> tuple[bool, bool]:
        """Upsert a spec version record."""
        record_id = version.record_id or f"{version.spec_number}:{version.version}:{version.source_name}"
        updated_version = version.model_copy(update={"record_id": record_id})
        existing = self._get_spec_version(record_id)
        if existing is None:
            self.connection.add("spec_versions", updated_version, pk="record_id")
            return True, False

        changed = self._spec_version_changed(existing, updated_version)
        self.connection.add("spec_versions", updated_version, pk="record_id")
        return False, changed

    def log_spec_download(self, download: SpecificationDownload) -> None:
        """Persist download/extraction outcomes for a spec version."""
        record_id = download.record_id or f"{download.spec_number}:{download.version}"
        # Convert Path objects to strings for SQLite compatibility
        updated_download = download.model_copy(
            update={
                "record_id": record_id,
                "checkout_path": str(download.checkout_path),
                "document_path": str(download.document_path),
                "attachment_paths": [str(p) for p in download.attachment_paths],
            }
        )
        self.connection.add("spec_downloads", updated_download, pk="record_id")

    def query_specs(self, filters: SpecQueryFilters) -> list[SpecQueryResult]:
        """Query stored spec metadata."""
        from tdoc_crawler.specs.query import SpecQueryResult  # noqa: PLC0415

        specs = self._spec_table_rows()

        if filters.spec_numbers:
            allowed = {value.strip() for value in filters.spec_numbers}
            specs = [spec for spec in specs if spec.spec_number in allowed]

        if filters.title:
            needle = filters.title.strip().lower()
            specs = [spec for spec in specs if needle in (spec.title or "").lower()]

        if filters.working_group:
            needle = filters.working_group.strip().lower()
            specs = [spec for spec in specs if (spec.working_group or "").lower() == needle]

        if filters.status:
            needle = filters.status.strip().lower()
            specs = [spec for spec in specs if (spec.status or "").lower() == needle]

        return [
            SpecQueryResult(
                spec_number=spec.spec_number,
                title=spec.title,
                status=spec.status,
                working_group=spec.working_group,
            )
            for spec in specs
        ]

    # ------------------------------------------------------------------
    # Crawl logging and statistics
    # ------------------------------------------------------------------
    def log_crawl_start(
        self,
        crawl_type: str,
        working_groups: Iterable[WorkingGroup] | None,
        incremental: bool,
    ) -> str:
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

    def clear_tdocs(self) -> int:
        """Clear all TDoc records from database.

        Returns:
            Number of TDocs deleted
        """
        if not self._table_exists("tdocs"):
            return 0

        cursor = self.connection._db.execute("SELECT COUNT(*) FROM tdocs")
        count = cursor.fetchone()[0]
        self.connection._db.execute("DELETE FROM tdocs")
        return count

    def clear_meetings(self) -> int:
        """Clear all meeting records from database.

        Returns:
            Number of meetings deleted
        """
        if not self._table_exists("meetings"):
            return 0

        cursor = self.connection._db.execute("SELECT COUNT(*) FROM meetings")
        count = cursor.fetchone()[0]
        self.connection._db.execute("DELETE FROM meetings")
        return count

    def clear_all_data(self) -> tuple[int, int]:
        """Clear all TDocs and meetings from database.

        Returns:
            Tuple of (tdocs_deleted, meetings_deleted)
        """
        tdocs_count = self.clear_tdocs()
        meetings_count = self.clear_meetings()
        return (tdocs_count, meetings_count)

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    def _prepare_tdoc(self, metadata: TDocMetadata) -> TDocMetadata:
        updates: dict[str, object] = {}
        if metadata.date_retrieved is None:
            updates["date_retrieved"] = utc_now()
        if updates:
            return metadata.model_copy(update=updates)
        return metadata

    def _prepare_meeting(self, metadata: MeetingMetadata) -> MeetingMetadata:
        if metadata.working_group is None and metadata.tbid:
            for working_group in WorkingGroup:
                if working_group.tbid == metadata.tbid:
                    return metadata.model_copy(update={"working_group": working_group})
        return metadata

    # ------------------------------------------------------------------
    # Data clearing methods
    # ------------------------------------------------------------------
    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        cursor = self.connection._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _ensure_reference_data(self) -> None:
        """Populate reference tables for working and subworking groups."""
        database = self.connection
        for record in WORKING_GROUP_RECORDS:
            database.add("working_groups", record, pk="tbid")
        for record in SUBWORKING_GROUP_RECORDS:
            database.add("subworking_groups", record, pk="subtb")

    def _table_rows(self, table: str) -> list:
        """Fetch all rows from a table using raw SQL to avoid pydantic_sqlite registry issues."""
        # Map table names to their model classes and safe names
        model_map = {
            "tdocs": TDocMetadata,
            "meetings": MeetingMetadata,
            "crawl_log": CrawlLogEntry,
            "specs": Specification,
            "spec_source_records": SpecificationSourceRecord,
            "spec_versions": SpecificationVersion,
            "spec_downloads": SpecificationDownload,
        }

        if table not in model_map:
            return []

        try:
            # Use raw SQL query with parameterized table name (whitelist approach)
            cursor = self.connection._db.execute(f"SELECT * FROM {table}")  # noqa: S608
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            model_class = model_map[table]

            # Convert rows to model instances
            result = []
            for row in rows:
                row_dict = dict(zip(columns, row, strict=False))
                # Handle datetime deserialization if needed
                for key, value in list(row_dict.items()):
                    if isinstance(value, str):
                        # Try to parse ISO datetime strings
                        try:
                            if "T" in value and value.endswith(("Z", "+00:00")):
                                row_dict[key] = datetime.fromisoformat(value)
                        except (ValueError, AttributeError):
                            pass
                result.append(model_class(**row_dict))
            return result
        except Exception:
            return []

    def _meeting_map(self) -> dict[int, MeetingMetadata]:
        return {meeting.meeting_id: meeting for meeting in self._table_rows("meetings")}

    def _get_meeting(self, meeting_id: int) -> MeetingMetadata | None:
        try:
            return self.connection.model_from_table("meetings", str(meeting_id))
        except KeyError:
            return None

    def _get_tdoc(self, tdoc_id: str) -> TDocMetadata | None:
        try:
            return self.connection.model_from_table("tdocs", tdoc_id.upper())  # type: ignore[arg-type]
        except KeyError:
            return None

    def _spec_table_rows(self) -> list[Specification]:
        return self._table_rows("specs")

    def _get_specification(self, spec_number: str) -> Specification | None:
        try:
            return self.connection.model_from_table("specs", spec_number)  # type: ignore[arg-type]
        except KeyError:
            return None

    def _get_spec_source_record(self, record_id: str) -> SpecificationSourceRecord | None:
        try:
            return self.connection.model_from_table("spec_source_records", record_id)  # type: ignore[arg-type]
        except KeyError:
            return None

    def _get_spec_version(self, record_id: str) -> SpecificationVersion | None:
        try:
            return self.connection.model_from_table("spec_versions", record_id)  # type: ignore[arg-type]
        except KeyError:
            return None

    @staticmethod
    def _tdoc_changed(current: TDocMetadata, candidate: TDocMetadata) -> bool:
        for field in TDocMetadata.model_fields:
            if field == "date_updated":
                continue
            if getattr(current, field) != getattr(candidate, field):
                return True
        return False

    @staticmethod
    def _meeting_changed(current: MeetingMetadata, candidate: MeetingMetadata) -> bool:
        for field in MeetingMetadata.model_fields:
            if field in {"updated_at", "last_synced", "tdoc_count"}:
                continue
            if getattr(current, field) != getattr(candidate, field):
                return True
        return False

    @staticmethod
    def _spec_changed(current: Specification, candidate: Specification) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in Specification.model_fields)

    @staticmethod
    def _spec_source_changed(current: SpecificationSourceRecord, candidate: SpecificationSourceRecord) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in SpecificationSourceRecord.model_fields)

    @staticmethod
    def _spec_version_changed(current: SpecificationVersion, candidate: SpecificationVersion) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in SpecificationVersion.model_fields)
