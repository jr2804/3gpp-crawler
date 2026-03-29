"""Base database class with common operations using Oxyde ORM."""

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Self
from uuid import uuid4

from oxyde import AsyncDatabase, Model
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
            url = f"sqlite:///{self.db_file.as_posix()}"
            self._database = AsyncDatabase(url, auto_register=True, overwrite=True)
            await self._database.connect()
            await self._ensure_tables_exist()
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
        )
        await CrawlLogEntry.objects.create(instance=entry)
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

        # Extract current schema from registered models
        schema = extract_current_schema(dialect="sqlite")

        # Build and execute CREATE TABLE IF NOT EXISTS for each table
        for table_name, table_def in schema.get("tables", {}).items():
            fields = table_def.get("fields", [])
            if not fields:
                continue

            # Build column definitions
            column_defs: list[str] = []
            pk_fields: list[str] = []
            for field in fields:
                if bool(field.get("primary_key", False)):
                    pk_fields.append(field["name"])

            for field in fields:
                col_name = field["name"]
                python_type = field["python_type"]

                # Map Python types to SQLite types
                sql_type: str
                if python_type == "int":
                    sql_type = "INTEGER"
                elif python_type == "str":
                    sql_type = "TEXT"
                elif python_type == "float":
                    sql_type = "REAL"
                elif python_type in ("datetime", "date"):
                    sql_type = "TEXT"
                elif python_type == "bool":
                    sql_type = "INTEGER"
                elif python_type == "bytes":
                    sql_type = "BLOB"
                elif python_type in ("list", "dict"):
                    sql_type = "TEXT"  # Store as JSON
                else:
                    sql_type = "TEXT"

                nullable = field.get("nullable", True)
                if not nullable:
                    sql_type += " NOT NULL"

                default = field.get("default")
                if default is not None and default != "NULL":
                    sql_type += f" DEFAULT {default}"

                is_pk = bool(field.get("primary_key", False))
                is_unique = bool(field.get("unique", False))
                if is_pk and len(pk_fields) == 1:
                    sql_type += " PRIMARY KEY"
                elif is_unique:
                    sql_type += " UNIQUE"

                column_defs.append(f"{col_name} {sql_type}")

            if len(pk_fields) > 1:
                pk_cols = ", ".join(pk_fields)
                column_defs.append(f"PRIMARY KEY ({pk_cols})")

            # Build complete CREATE TABLE IF NOT EXISTS statement
            columns_sql = ", ".join(column_defs)
            create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"

            # Execute the SQL using Oxyde's IR format for raw SQL
            raw_ir = {"proto": 1, "op": "raw", "table": "", "sql": create_sql}
            await self._database.execute(raw_ir)

    async def _ensure_reference_data(self) -> None:
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

    async def _table_rows(self, model_class: type) -> list:
        """Fetch all rows for a given model class."""
        try:
            return await model_class.objects.all()
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
                count = await model_class.objects.count()
                await model_class.objects.delete()
                counts[table] = count
            except (OSError, ValueError) as exc:
                _logger.error("Failed to clear table %s: %s", table, exc)
                counts[table] = 0
        return counts


__all__ = ["DocDatabase"]
