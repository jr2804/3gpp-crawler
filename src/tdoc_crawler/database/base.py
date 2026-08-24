"""Base database class with common operations using Oxyde ORM."""

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from uuid import uuid4

from oxyde import AsyncDatabase, Model, execute_raw
from oxyde.migrations import extract_current_schema

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

_PYTHON_TO_SQLITE_TYPE: dict[str, str] = {
    "int": "INTEGER",
    "str": "TEXT",
    "float": "REAL",
    "datetime": "TEXT",
    "date": "TEXT",
    "bool": "INTEGER",
    "bytes": "BLOB",
    "list": "TEXT",
    "dict": "TEXT",
}

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

    # ------------------------------------------------------------------
    # Context manager lifecycle
    # ------------------------------------------------------------------
    async def __aenter__(self) -> Self:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{self.db_file.as_posix()}"
            self._database = AsyncDatabase(url, auto_register=True, overwrite=True)
            await self._database.connect()
            await self._ensure_tables_exist()
            await self._ensure_reference_data()
        except Exception as exc:
            msg = "database-initialization-failed"
            raise DatabaseError(msg, detail=str(exc)) from exc
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: object | None) -> None:
        if self._database is not None:
            with contextlib.suppress(RuntimeError):
                # Pool already closed by nested overwrite
                await self._database.disconnect()
        self._database = None

    # ------------------------------------------------------------------
    # Core accessors and utilities
    # ------------------------------------------------------------------
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

    @staticmethod
    async def log_crawl_start(crawl_type: str, filters: list[str] | None, incremental: bool) -> str:
        """Log the start of a crawl operation.

        Args:
            crawl_type: Type of crawl (e.g., 'tdoc', 'meeting', 'spec')
            filters: List of filter strings applied to the crawl
            incremental: Whether this is an incremental crawl

        Returns:
            The ID of the created crawl log entry
        """
        log_id = f"{crawl_type}-{uuid4().hex}"
        entry = CrawlLogEntry(
            log_id=log_id,
            crawl_type=crawl_type,
            working_groups=filters or [],
            incremental=incremental,
            start_time=datetime.now(),
            end_time=None,
            items_added=0,
            items_updated=0,
            errors_count=0,
            status="RUNNING",
            # oxyde create() excludes unset fields; created_at has no SQL default
            created_at=datetime.now(UTC),
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
        """Log the end of a crawl operation.

        Args:
            crawl_id: ID of the crawl log entry to update
            items_added: Number of new items added
            items_updated: Number of existing items updated
            errors_count: Number of errors encountered
        """
        await CrawlLogEntry.objects.filter(log_id=crawl_id).update(
            end_time=datetime.now(),
            items_added=items_added,
            items_updated=items_updated,
            errors_count=errors_count,
            status="COMPLETED",
        )

    async def _ensure_tables_exist(self) -> None:
        """Create database tables from Oxyde models if they don't exist.

        Uses extract_current_schema() to get table definitions from registered models,
        then creates tables using raw SQL CREATE IF NOT EXISTS statements.
        """
        if self._database is None:
            return

        schema = extract_current_schema(dialect="sqlite")

        for table_name, table_def in schema.get("tables", {}).items():
            fields = table_def.get("fields", [])
            if not fields:
                continue

            column_defs, pk_fields = _build_column_defs(fields)
            if len(pk_fields) > 1:
                column_defs.append(f"PRIMARY KEY ({', '.join(pk_fields)})")

            columns_sql = ", ".join(column_defs)
            create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"
            raw_ir = {"proto": 1, "op": "raw", "table": "", "sql": create_sql}
            await self._database.execute(raw_ir)

        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """Apply incremental schema migrations for existing databases."""
        if self._database is None:
            return

        # Compare the model's declared columns against the live table.
        # extract_current_schema() is the same source of truth used by
        # _ensure_tables_exist() for CREATE TABLE — so adding a field to the
        # model is the only step required to ship a new migration.
        new_schema = extract_current_schema(dialect="sqlite")
        migrations: list[tuple[str, str, str]] = []
        for table_name, table_def in new_schema.get("tables", {}).items():
            desired_cols = {f["name"] for f in table_def.get("fields", [])}
            rows = await execute_raw(f"PRAGMA table_info({table_name})")
            existing_cols = {row["name"] for row in rows}
            for col in sorted(desired_cols - existing_cols):
                # python_type drives the column type; default to TEXT (covers
                # str / datetime / int / bool — SQLite is dynamically typed).
                field = next(f for f in table_def["fields"] if f["name"] == col)
                py_type = field.get("python_type", "str")
                sqlite_type = "INTEGER" if py_type == "int" else "TEXT"
                migrations.append(
                    (
                        table_name,
                        col,
                        f"ALTER TABLE {table_name} ADD COLUMN {col} {sqlite_type}",
                    )
                )

        for table_name, column_name, alter_sql in migrations:
            try:
                _logger.info("Migrating %s: adding column %s", table_name, column_name)
                await execute_raw(alter_sql)
            except Exception as exc:
                _logger.warning("Migration failed for %s.%s: %s", table_name, column_name, exc)

    @staticmethod
    async def _ensure_reference_data() -> None:
        """Populate reference tables for working and subworking groups."""
        for record in WORKING_GROUP_RECORDS:
            existing = await WorkingGroupRecord.objects.filter(tbid=record.tbid).first()
            if existing is None:
                oxyde_record = WorkingGroupRecord(
                    tbid=record.tbid,
                    code=record.code,
                    name=record.name,
                )
                await WorkingGroupRecord.objects.create(instance=oxyde_record)
        for record in SUBWORKING_GROUP_RECORDS:
            existing = await SubWorkingGroupRecord.objects.filter(subtb=record.subtb).first()
            if existing is None:
                oxyde_record = SubWorkingGroupRecord(
                    subtb=record.subtb,
                    tbid=record.tbid,
                    code=record.code,
                    name=record.name,
                )
                await SubWorkingGroupRecord.objects.create(instance=oxyde_record)

    @staticmethod
    async def _table_rows(model_class: type) -> list:
        """Fetch all rows for a given model class."""
        try:
            return await model_class.objects.all()
        except Exception as exc:
            _logger.exception("Failed to read table for %s: %s", model_class.__name__, exc)
            msg = "table-read-failed"
            raise DatabaseError(msg, detail=f"Model '{model_class.__name__}': {exc}") from exc

    @staticmethod
    async def _clear_tables(table_names: str | Iterable[str]) -> dict[str, int]:
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
                count = await model_class.objects.count()
                table_name = model_class.get_table_name()
                # table_name derives from registered models, never user input
                await execute_raw(f"DELETE FROM {table_name}", using="default")  # noqa: S608
                counts[table] = count
            except (OSError, ValueError) as exc:
                _logger.exception("Failed to clear table %s: %s", table, exc)
                counts[table] = 0
        return counts


def _build_column_defs(fields: list[dict]) -> tuple[list[str], list[str]]:
    """Build all column definitions and collect primary key field names.

    Returns:
        Tuple of (column SQL strings, primary key field names).
    """
    pk_fields = [f["name"] for f in fields if bool(f.get("primary_key", False))]
    column_defs = [_build_column_sql(f, len(pk_fields)) for f in fields]
    return column_defs, pk_fields


def _build_column_sql(field: dict, pk_count: int) -> str:
    """Build a single column SQL definition from a schema field dict."""
    col_name = field["name"]
    sql_type = _PYTHON_TO_SQLITE_TYPE.get(field["python_type"], "TEXT")

    if not field.get("nullable", True):
        sql_type += " NOT NULL"

    default = field.get("default")
    if default is not None and default != "NULL":
        sql_type += f" DEFAULT {default}"

    is_pk = bool(field.get("primary_key", False))
    is_unique = bool(field.get("unique", False))
    if is_pk and pk_count == 1:
        sql_type += " PRIMARY KEY"
    elif is_unique:
        sql_type += " UNIQUE"

    return f"{col_name} {sql_type}"


__all__ = ["DocDatabase"]
