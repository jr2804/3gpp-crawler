"""Protocol definitions for database factory abstractions."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase


@runtime_checkable
class DatabaseFactory(Protocol):
    """Protocol for creating database instances."""

    def get_tdoc_db(self) -> TDocDatabase:
        """Return an open TDocDatabase context manager."""
        ...

    def get_spec_db(self) -> SpecDatabase:
        """Return an open SpecDatabase context manager."""
        ...

    def get_meeting_db(self) -> TDocDatabase:
        """Return an open TDocDatabase for meeting operations (TDocDatabase inherits MeetingDatabase)."""
        ...


class DefaultDatabaseFactory:
    """Default implementation of DatabaseFactory backed by a SQLite file path."""

    def __init__(self, db_file: Path) -> None:
        """Initialize with path to the SQLite database file.

        Args:
            db_file: Path to the SQLite database file.
        """
        self._db_file = db_file

    def get_tdoc_db(self) -> TDocDatabase:
        """Return a TDocDatabase for the configured database file.

        Returns:
            A TDocDatabase instance (not yet opened; use as context manager).
        """
        return TDocDatabase(self._db_file)

    def get_spec_db(self) -> SpecDatabase:
        """Return a SpecDatabase for the configured database file.

        Returns:
            A SpecDatabase instance (not yet opened; use as context manager).
        """
        return SpecDatabase(self._db_file)

    def get_meeting_db(self) -> TDocDatabase:
        """Return a TDocDatabase for meeting operations.

        TDocDatabase inherits from MeetingDatabase, so it provides all meeting ops.

        Returns:
            A TDocDatabase instance (not yet opened; use as context manager).
        """
        return TDocDatabase(self._db_file)


__all__ = ["DatabaseFactory", "DefaultDatabaseFactory"]
