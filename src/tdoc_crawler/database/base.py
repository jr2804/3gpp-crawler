"""Database facade.

Schema is owned by Oxyde: tables are created from registered models via
``oxyde.db.schema.create_tables()`` on every fresh database. No migrations
— an existing DB whose schema does not match the current models is a hard
error pointing the caller at regeneration.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from uuid import uuid4

from oxyde import AsyncDatabase, execute_raw
from oxyde.db.schema import create_tables
from oxyde.migrations import extract_current_schema

from tdoc_crawler.database.archives import clear_archive_members
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.oxyde_models import (
    CrawlLogEntry,
    SubWorkingGroupRecord,
    TDocMetadata,
    WorkingGroupRecord,
)
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.archives import ArchiveKind
from tdoc_crawler.models.subworking_groups import SUBWORKING_GROUP_RECORDS
from tdoc_crawler.models.working_groups import WORKING_GROUP_RECORDS

_logger = get_logger(__name__)


class DocDatabase:
    """High-level facade for all database operations using Oxyde ORM."""

    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file
        self.cache_dir = db_file.parent
        self._database: AsyncDatabase | None = None

    @property
    def connection(self) -> AsyncDatabase:
        """Return the underlying AsyncDatabase connection.

        Raises:
            DatabaseError: If accessed outside of context manager
        """
        if self._database is None:
            raise DatabaseError.connection_not_open()
        return self._database

    async def __aenter__(self) -> Self:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{self.db_file.as_posix()}"
        self._database = AsyncDatabase(url, auto_register=True, overwrite=True)
        await self._database.connect()
        await self._ensure_schema()
        await self._seed_reference_data()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: object | None) -> None:
        if self._database is not None:
            with contextlib.suppress(RuntimeError):
                # Pool already closed by nested overwrite
                await self._database.disconnect()
        self._database = None

    async def clear_tdocs(self) -> int:
        """Clear all TDoc records (and their archive listings) from database."""
        counts = await self._clear_tables([TDocMetadata])
        await clear_archive_members(ArchiveKind.TDOC)
        return counts.get(TDocMetadata.get_table_name(), 0)

    # ------------------------------------------------------------------
    # Crawl logging
    # ------------------------------------------------------------------
    @staticmethod
    async def log_crawl_start(crawl_type: str, filters: list[str] | None, incremental: bool) -> str:
        """Log the start of a crawl operation."""
        log_id = f"{crawl_type}-{uuid4().hex}"
        now = datetime.now(UTC)
        entry = CrawlLogEntry(
            log_id=log_id,
            crawl_type=crawl_type,
            working_groups=filters or [],
            incremental=incremental,
            start_time=now,
            end_time=None,
            items_added=0,
            items_updated=0,
            errors_count=0,
            status="RUNNING",
            # oxyde create() excludes unset fields; created_at has no SQL default
            created_at=now,
        )
        await CrawlLogEntry.objects.create(instance=entry)
        return entry.log_id

    @staticmethod
    async def log_crawl_end(
        crawl_id: str,
        items_added: int,
        items_updated: int,
        errors_count: int,
    ) -> None:
        """Log the end of a crawl operation."""
        await CrawlLogEntry.objects.filter(log_id=crawl_id).update(
            end_time=datetime.now(),
            items_added=items_added,
            items_updated=items_updated,
            errors_count=errors_count,
            status="COMPLETED",
        )

    async def _ensure_schema(self) -> None:
        """Verify the live DB schema matches the models; create if empty.

        Two paths:

        * Empty DB (``sqlite_master`` has no ``tdocmetadata`` table) → call
          ``create_tables()`` and we're done.
        * Existing DB → diff model columns against live columns. If they
          match, return. Otherwise raise a hard error — we do not run
          migrations, by design.
        """
        if self._database is None:
            return
        sentinel = TDocMetadata.get_table_name()
        tables = await execute_raw("SELECT name FROM sqlite_master WHERE type='table'")
        if not any(t["name"] == sentinel for t in tables):
            await create_tables(self._database)
            return

        expected = extract_current_schema(dialect="sqlite").get("tables", {})
        missing: list[tuple[str, str]] = []  # (table, column)
        for table_name, table_def in expected.items():
            rows = await execute_raw(f"PRAGMA table_info({table_name})")
            existing = {row["name"] for row in rows}
            desired = {f["name"] for f in table_def.get("fields", [])}
            for col in sorted(desired - existing):
                missing.append((table_name, col))
        if missing:
            details = ", ".join(f"{t}.{c}" for t, c in missing)
            msg = "schema-mismatch"
            raise DatabaseError(
                msg,
                detail=(
                    f"Database schema is out of date (missing: {details}). Delete the database file and re-crawl, or set TDC_CACHE_DIR to a fresh directory."
                ),
            )

    @staticmethod
    async def _seed_reference_data() -> None:
        """Populate reference tables for working and subworking groups."""
        for record in WORKING_GROUP_RECORDS:
            existing = await WorkingGroupRecord.objects.filter(tbid=record.tbid).first()
            if existing is None:
                await WorkingGroupRecord.objects.create(
                    instance=WorkingGroupRecord(
                        tbid=record.tbid,
                        code=record.code,
                        name=record.name,
                    )
                )
        for record in SUBWORKING_GROUP_RECORDS:
            existing = await SubWorkingGroupRecord.objects.filter(subtb=record.subtb).first()
            if existing is None:
                await SubWorkingGroupRecord.objects.create(
                    instance=SubWorkingGroupRecord(
                        subtb=record.subtb,
                        tbid=record.tbid,
                        code=record.code,
                        name=record.name,
                    )
                )

    @staticmethod
    async def _clear_tables(models: Iterable[type]) -> dict[str, int]:
        """Clear the given tables; returns table_name -> deleted row count.

        Each arg is an Oxyde ``Model`` subclass — the SQL table name comes
        from ``Model.get_table_name()`` so callers don't need to know the
        physical name.
        """
        counts: dict[str, int] = {}
        for model in models:
            table = model.get_table_name()
            try:
                count = await model.objects.count()
                await execute_raw(f"DELETE FROM {table}", using="default")  # noqa: S608
                counts[table] = count
            except (OSError, ValueError) as exc:
                _logger.exception("Failed to clear table %s: %s", table, exc)
                counts[table] = 0
        return counts

    @staticmethod
    async def _table_rows(model_class: type) -> list:
        """Fetch all rows for a given model class."""
        try:
            return await model_class.objects.all()
        except Exception as exc:
            _logger.exception("Failed to read table for %s: %s", model_class.__name__, exc)
            msg = "table-read-failed"
            raise DatabaseError(msg, detail=f"Model '{model_class.__name__}': {exc}") from exc


__all__ = ["DocDatabase"]
