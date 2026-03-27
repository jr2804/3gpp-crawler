"""Base database class with common operations using Oxyde ORM."""

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Self

from oxyde import AsyncDatabase, Model

from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.oxyde_models import (
    CrawlLogEntry,
    MeetingMetadata,
    Specification,
    SpecificationDownload,
    SpecificationSourceRecord,
    SpecificationVersion,
    SubWorkingGroupRecord,
    TDocMetadata,
    WorkingGroupRecord,
)
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.subworking_groups import SUBWORKING_GROUP_RECORDS
from tdoc_crawler.models.working_groups import WORKING_GROUP_RECORDS

_logger = get_logger(__name__)


class DocDatabase:
    """High-level facade for all database operations using Oxyde ORM."""

    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file
        self.cache_dir = db_file.parent
        self._database: AsyncDatabase | None = None

    # ------------------------------------------------------------------
    # Context manager lifecycle
    # ------------------------------------------------------------------
    async def __aenter__(self) -> Self:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._database = AsyncDatabase(self.db_file)
            await self._database.connect()
            # Register all models with the database
            self._database.register(WorkingGroupRecord)
            self._database.register(SubWorkingGroupRecord)
            self._database.register(CrawlLogEntry)
            self._database.register(MeetingMetadata)
            self._database.register(TDocMetadata)
            self._database.register(Specification)
            self._database.register(SpecificationSourceRecord)
            self._database.register(SpecificationVersion)
            self._database.register(SpecificationDownload)
            await self._ensure_reference_data()
        except Exception as exc:
            raise DatabaseError("database-initialization-failed", detail=str(exc)) from exc
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: object | None) -> None:
        if self._database is not None:
            await self._database.disconnect()
        self._database = None

    # ------------------------------------------------------------------
    # Core accessors and utilities
    # ------------------------------------------------------------------
    @property
    def connection(self) -> AsyncDatabase:
        """Expose the underlying AsyncDatabase instance (read-only)."""
        if self._database is None:
            raise DatabaseError.connection_not_open()
        return self._database

    async def clear_tdocs(self) -> int:
        """Clear all TDoc records from database.

        Returns:
            Number of TDocs deleted
        """
        counts = await self._clear_tables(["tdocs"])
        return counts.get("tdocs", 0)

    async def clear_specs(self) -> dict[str, int]:
        """Clear all spec-related records from database.

        Returns:
            Mapping of table name to deleted row count.
        """
        return await self._clear_tables(["spec_downloads", "spec_versions", "spec_source_records", "specs"])

    async def log_crawl_start(self, crawl_type: str, filters: list[str] | None, incremental: bool) -> str:
        """Log the start of a crawl operation.

        Args:
            crawl_type: Type of crawl (e.g., 'tdoc', 'meeting', 'spec')
            filters: List of filter strings applied to the crawl
            incremental: Whether this is an incremental crawl

        Returns:
            The ID of the created crawl log entry
        """
        entry = CrawlLogEntry(
            crawl_type=crawl_type,
            working_groups=filters or [],
            incremental=incremental,
            start_time=datetime.now(),
            end_time=None,
            items_added=0,
            items_updated=0,
            errors_count=0,
            status="RUNNING",
        )
        await self.connection.save(entry)
        return entry.log_id

    async def log_crawl_end(
        self,
        crawl_id: str,
        items_added: int,
        items_updated: int,
        errors_count: int,
    ) -> None:
        """Log the end of a crawl operation.

        Args:
            crawl_id: ID of the crawl log entry to update
            items_added: Number of new items added
            items_updated: Number of existing items updated
            errors_count: Number of errors encountered
        """
        entry = await self.connection.get(CrawlLogEntry, crawl_id)
        if entry:
            entry.end_time = datetime.now()
            entry.items_added = items_added
            entry.items_updated = items_updated
            entry.errors_count = errors_count
            entry.status = "COMPLETED"
            await self.connection.save(entry)

    async def _ensure_reference_data(self) -> None:
        """Populate reference tables for working and subworking groups."""
        for record in WORKING_GROUP_RECORDS:
            oxyde_record = WorkingGroupRecord(
                tbid=record.tbid,
                code=record.code,
                name=record.name,
            )
            await self.connection.save(oxyde_record)
        for record in SUBWORKING_GROUP_RECORDS:
            oxyde_record = SubWorkingGroupRecord(
                subtb=record.subtb,
                tbid=record.tbid,
                code=record.code,
                name=record.name,
            )
            await self.connection.save(oxyde_record)

    async def _table_rows(self, model_class: type) -> list:
        """Fetch all rows for a given model class."""
        try:
            return await self.connection.all(model_class)
        except Exception as exc:
            _logger.error("Failed to read table for %s: %s", model_class.__name__, exc)
            raise DatabaseError("table-read-failed", detail=f"Model '{model_class.__name__}': {exc}") from exc

    async def _clear_tables(self, table_names: str | Iterable[str]) -> dict[str, int]:
        """Clear specified tables from database.

        Args:
            table_names: Iterable of table names (or single table name) to clear

        Returns:
            Mapping of table name to deleted row count.
        """
        if isinstance(table_names, str):
            table_names = [table_names]

        counts: dict[str, int] = {}
        # Map table names to model classes
        table_to_model: dict[str, type[Model]] = {
            "tdocs": TDocMetadata,
            "meetings": MeetingMetadata,
            "crawl_log": CrawlLogEntry,
            "specs": Specification,
            "spec_source_records": SpecificationSourceRecord,
            "spec_versions": SpecificationVersion,
            "spec_downloads": SpecificationDownload,
            "working_groups": WorkingGroupRecord,
            "subworking_groups": SubWorkingGroupRecord,
        }

        for table in table_names:
            model_class = table_to_model.get(table)
            if model_class is None:
                counts[table] = 0
                continue
            try:
                count = await self.connection.count(model_class)
                await self.connection.delete_all(model_class)
                counts[table] = count
            except (OSError, ValueError) as exc:
                _logger.error("Failed to clear table %s: %s", table, exc)
                counts[table] = 0
        return counts


__all__ = ["DocDatabase"]
