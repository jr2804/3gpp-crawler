"""Database connection management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType

from tdoc_crawler.database import logging as db_logging
from tdoc_crawler.database import meetings as db_meetings
from tdoc_crawler.database import statistics as db_statistics
from tdoc_crawler.database import tdocs as db_tdocs
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.schema import configure_connection, initialize_schema
from tdoc_crawler.models import (
    MeetingMetadata,
    MeetingQueryConfig,
    QueryConfig,
    TDocMetadata,
    WorkingGroup,
)


class TDocDatabase:
    """Context manager for TDoc database operations.

    This class provides a high-level API for all database operations,
    delegating to specialized modules for implementation.

    Usage:
        with TDocDatabase(db_path) as database:
            database.upsert_tdoc(metadata)
            results = database.query_tdocs(config)
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> TDocDatabase:
        """Enter context manager and open database connection.

        Returns:
            Self with active connection

        Raises:
            DatabaseError: If connection fails
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            configure_connection(self._connection)
            initialize_schema(self._connection)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Database connection failed: {exc}") from exc
        else:
            return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager and close database connection.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get active database connection.

        Returns:
            SQLite connection

        Raises:
            DatabaseError: If connection not open
        """
        if self._connection is None:
            raise DatabaseError.connection_not_open()
        return self._connection

    # TDoc operations
    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        """Insert or update a TDoc record."""
        return db_tdocs.upsert_tdoc(self.connection, metadata)

    def bulk_upsert_tdocs(self, tdocs: Iterable[TDocMetadata]) -> tuple[int, int]:
        """Bulk insert or update TDoc records."""
        return db_tdocs.bulk_upsert_tdocs(self.connection, tdocs)

    def query_tdocs(self, config: QueryConfig) -> list[TDocMetadata]:
        """Query TDocs with filters and sorting."""
        return db_tdocs.query_tdocs(self.connection, config)

    def get_existing_tdoc_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[str]:
        """Get all existing TDoc IDs."""
        return db_tdocs.get_existing_tdoc_ids(self.connection, working_groups)

    def get_processed_meetings(
        self,
        working_groups: Iterable[WorkingGroup] | None = None,
        subgroups: Iterable[str] | None = None,
    ) -> set[int]:
        """Get meeting IDs that have been crawled for TDocs."""
        return db_tdocs.get_processed_meetings(self.connection, working_groups, subgroups)

    def cache_invalid_tdoc(
        self,
        tdoc_id: str,
        url: str,
        working_group: WorkingGroup,
        subgroup: str,
    ) -> None:
        """Cache a TDoc that failed portal validation."""
        db_tdocs.cache_invalid_tdoc(self.connection, tdoc_id, url, working_group, subgroup)

    def get_cached_invalid_tdocs(self) -> set[str]:
        """Get all TDoc IDs that have been cached as invalid."""
        return db_tdocs.get_cached_invalid_tdocs(self.connection)

    # Meeting operations
    def upsert_meeting(self, metadata: MeetingMetadata) -> tuple[bool, bool]:
        """Insert or update a meeting record."""
        return db_meetings.upsert_meeting(self.connection, metadata)

    def bulk_upsert_meetings(self, meetings: Iterable[MeetingMetadata]) -> tuple[int, int]:
        """Bulk insert or update meeting records."""
        return db_meetings.bulk_upsert_meetings(self.connection, meetings)

    def query_meetings(self, config: MeetingQueryConfig) -> list[MeetingMetadata]:
        """Query meetings with filters and sorting."""
        return db_meetings.query_meetings(self.connection, config)

    def get_existing_meeting_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[int]:
        """Get all existing meeting IDs."""
        return db_meetings.get_existing_meeting_ids(self.connection, working_groups)

    def get_subgroup_by_code(self, code: str) -> dict | None:
        """Get subgroup information by code."""
        return db_meetings.get_subgroup_by_code(self.connection, code)

    # Crawl logging
    def log_crawl_start(
        self,
        crawl_type: str,
        working_groups: Iterable[WorkingGroup] | None = None,
        incremental: bool = False,
    ) -> int:
        """Log the start of a crawl operation."""
        wg_list = working_groups if working_groups is not None else []
        return db_logging.log_crawl_start(self.connection, crawl_type, wg_list, incremental)

    def log_crawl_end(
        self,
        crawl_id: int,
        *,
        items_added: int,
        items_updated: int,
        errors_count: int,
        status: str = "COMPLETED",
    ) -> None:
        """Log the end of a crawl operation."""
        db_logging.log_crawl_end(
            self.connection,
            crawl_id,
            items_added=items_added,
            items_updated=items_updated,
            errors_count=errors_count,
            status=status,
        )

    # Statistics
    def get_statistics(self) -> dict:
        """Get comprehensive database statistics (as dict for backward compatibility)."""
        from dataclasses import asdict

        stats = db_statistics.get_statistics(self.connection)
        result = asdict(stats)
        # Rename field for backward compatibility
        result["by_working_group"] = result.pop("working_group_breakdown")
        return result
