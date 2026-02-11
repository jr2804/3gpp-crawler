"""Base database class with common operations."""

import json
import logging
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic_sqlite import DataBase

from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.meetings.models import MeetingMetadata
from tdoc_crawler.models.crawl_log import CrawlLogEntry
from tdoc_crawler.specs.models import (
    Specification,
    SpecificationDownload,
    SpecificationSourceRecord,
    SpecificationVersion,
)
from tdoc_crawler.models.subworking_groups import SUBWORKING_GROUP_RECORDS
from tdoc_crawler.models.working_groups import WORKING_GROUP_RECORDS
from tdoc_crawler.tdocs.models import TDocMetadata

_logger = logging.getLogger(__name__)


class DocDatabase:
    """High-level facade for all database operations."""

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

    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file
        self.cache_dir = db_file.parent
        self._database: DataBase | None = None

    # ------------------------------------------------------------------
    # Context manager lifecycle
    # ------------------------------------------------------------------
    def __enter__(self) -> Self:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._database = DataBase(self.db_file)
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

    def clear_all_data(self) -> dict[str, int]:
        """Clear all TDocs and meetings from database.

        Returns:
            Mapping of table name to deleted count
        """
        return self._clear_tables(self.model_map.keys())

    def clear_tdocs(self) -> int:
        """Clear all TDoc records from database.

        Returns:
            Number of TDocs deleted
        """
        counts = self._clear_tables(["tdocs"])
        return counts.get("tdocs", 0)

    def clear_meetings(self) -> int:
        """Clear all meeting records from database.

        Returns:
            Number of meetings deleted
        """
        counts = self._clear_tables(["meetings"])
        return counts.get("meetings", 0)

    def clear_specs(self) -> dict[str, int]:
        """Clear all spec-related records from database.

        Returns:
            Mapping of table name to deleted row count.
        """
        return self._clear_tables(["spec_downloads", "spec_versions", "spec_source_records", "specs"])

    def log_crawl_start(self, crawl_type: str, filters: list[str] | None, incremental: bool) -> int:
        """Log the start of a crawl operation.

        Args:
            crawl_type: Type of crawl (e.g., 'tdoc', 'meeting', 'spec')
            filters: List of filter strings applied to the crawl
            incremental: Whether this is an incremental crawl

        Returns:
            The ID of the created crawl log entry
        """
        from tdoc_crawler.models import CrawlLogEntry

        entry = CrawlLogEntry(
            crawl_type=crawl_type,
            filters=json.dumps(filters or []),
            incremental=incremental,
            start_time=datetime.now(),
            end_time=None,
            items_added=0,
            items_updated=0,
            errors_count=0,
        )
        self.connection.add("crawl_log", entry, pk=True)
        return entry.id

    def log_crawl_end(
        self,
        crawl_id: int,
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
        self.connection._db.execute(
            "UPDATE crawl_log SET end_time = ?, items_added = ?, items_updated = ?, errors_count = ? WHERE id = ?",
            (datetime.now(), items_added, items_updated, errors_count, crawl_id),
        )
        self.connection._db.commit()

    def _ensure_reference_data(self) -> None:
        """Populate reference tables for working and subworking groups."""
        database = self.connection
        for record in WORKING_GROUP_RECORDS:
            database.add("working_groups", record, pk="tbid")
        for record in SUBWORKING_GROUP_RECORDS:
            database.add("subworking_groups", record, pk="subtb")

    def _table_rows(self, table: str) -> list:
        """Fetch all rows from a table using raw SQL to avoid pydantic_sqlite registry issues."""
        if table not in self.model_map:
            return []

        try:
            # Use raw SQL query with parameterized table name (whitelist approach)
            cursor = self.connection._db.execute(f"SELECT * FROM {table}")  # noqa: S608
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            model_class = self.model_map[table]

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
                        except ValueError, AttributeError:
                            pass
                if table == "spec_source_records":
                    metadata_payload = row_dict.get("metadata_payload")
                    if isinstance(metadata_payload, str):
                        try:
                            row_dict["metadata_payload"] = json.loads(metadata_payload)
                        except json.JSONDecodeError:
                            row_dict["metadata_payload"] = {}
                    versions = row_dict.get("versions")
                    if isinstance(versions, str):
                        try:
                            row_dict["versions"] = json.loads(versions)
                        except json.JSONDecodeError:
                            row_dict["versions"] = []
                result.append(model_class(**row_dict))
            return result
        except Exception:
            return []

    def _clear_tables(self, table_names: str | Iterable[str]) -> dict[str, int]:
        """Clear specified tables from database.

        Args:
            table_names: Iterable of table names (or single table name) to clear

        Returns:
            Mapping of table name to deleted row count.
        """
        if isinstance(table_names, str):
            table_names = [table_names]

        counts: dict[str, int] = {}
        for table in table_names:
            if not self._table_exists(table):
                counts[table] = 0
                continue
            cursor = self.connection._db.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            counts[table] = cursor.fetchone()[0]
            self.connection._db.execute(f"DELETE FROM {table}")  # noqa: S608
        return counts

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


__all__ = ["DocDatabase"]
