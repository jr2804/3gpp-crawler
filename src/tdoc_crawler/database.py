"""SQLite-backed persistence layer for TDoc crawler metadata."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tdoc_crawler.models import (
    MeetingMetadata,
    MeetingQueryConfig,
    MeetingRecord,
    QueryConfig,
    SortOrder,
    TDocMetadata,
    TDocRecord,
    WorkingGroup,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class DatabaseError(RuntimeError):
    """Raised when a database constraint or execution fails."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        message = f"{code}:{detail}" if detail else code
        super().__init__(message)

    @classmethod
    def connection_not_open(cls) -> DatabaseError:
        return cls("connection-not-open")

    @classmethod
    def crawl_log_persist_failed(cls) -> DatabaseError:
        return cls("crawl-log-persist-failed")

    @classmethod
    def parse_failure(cls, entity: str, detail: str) -> DatabaseError:
        return cls(f"{entity}-parse-failed", detail=detail)

    @classmethod
    def missing_datetime(cls) -> DatabaseError:
        return cls("missing-required-datetime")


class TDocDatabase:
    """Typed wrapper around an SQLite database storing meetings and TDocs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> TDocDatabase:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._configure_connection(self._conn)
        self._initialize_schema(self._conn)
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
        if self._conn is None:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError.connection_not_open()
        return self._conn

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

    @staticmethod
    def _initialize_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema_version INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO schema_meta (id, schema_version)
            VALUES (1, ?)
            """,
            (SCHEMA_VERSION,),
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL UNIQUE,
                working_group TEXT NOT NULL,
                subgroup TEXT,
                short_name TEXT NOT NULL,
                title TEXT,
                start_date TEXT,
                end_date TEXT,
                location TEXT,
                files_url TEXT,
                portal_url TEXT,
                last_synced TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_meetings_wg ON meetings(working_group)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meetings_start_date ON meetings(start_date)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tdocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tdoc_id TEXT NOT NULL UNIQUE COLLATE NOCASE,
                url TEXT NOT NULL,
                working_group TEXT NOT NULL,
                subgroup TEXT,
                meeting TEXT,
                meeting_id INTEGER,
                file_size INTEGER,
                document_type TEXT,
                checksum TEXT,
                source_path TEXT,
                date_created TEXT,
                date_retrieved TEXT NOT NULL,
                date_updated TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id)
            )
            """
        )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_wg ON tdocs(working_group)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_meeting_id ON tdocs(meeting_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_date ON tdocs(date_retrieved)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawl_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                working_groups TEXT NOT NULL,
                incremental INTEGER NOT NULL,
                items_added INTEGER DEFAULT 0,
                items_updated INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                status TEXT NOT NULL
            )
            """
        )

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        cursor = self.connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def log_crawl_start(self, crawl_type: str, working_groups: Iterable[WorkingGroup], incremental: bool) -> int:
        now = datetime.now(UTC).isoformat()
        wg_list = ",".join(sorted({wg.value for wg in working_groups}))
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO crawl_log (crawl_type, start_time, working_groups, incremental, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (crawl_type, now, wg_list, int(incremental), "RUNNING"),
            )
            self.connection.commit()
            crawl_id = cursor.lastrowid
        if crawl_id is None:
            raise DatabaseError.crawl_log_persist_failed()
        return int(crawl_id)

    def log_crawl_end(
        self,
        crawl_id: int,
        *,
        items_added: int,
        items_updated: int,
        errors_count: int,
        status: str = "COMPLETED",
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE crawl_log
                   SET end_time = ?,
                       items_added = ?,
                       items_updated = ?,
                       errors_count = ?,
                       status = ?
                 WHERE id = ?
                """,
                (now, items_added, items_updated, errors_count, status, crawl_id),
            )
            self.connection.commit()

    def upsert_meeting(self, meeting: MeetingMetadata) -> tuple[bool, bool]:
        record = MeetingRecord.from_metadata(meeting)
        now = datetime.now(UTC).isoformat()

        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM meetings WHERE meeting_id = ?",
                (record.meeting_id,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.execute(
                    """
                    INSERT INTO meetings (
                        meeting_id, working_group, subgroup, short_name, title, start_date, end_date,
                        location, files_url, portal_url, last_synced, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.meeting_id,
                        record.working_group.value,
                        record.subgroup,
                        record.short_name,
                        record.title,
                        self._date_to_text(record.start_date),
                        self._date_to_text(record.end_date),
                        record.location,
                        record.files_url,
                        record.portal_url,
                        record.last_synced.isoformat(),
                        now,
                        now,
                    ),
                )
                self.connection.commit()
                return True, False

            changed = any((
                existing["working_group"] != record.working_group.value,
                existing["subgroup"] != record.subgroup,
                existing["short_name"] != record.short_name,
                existing["title"] != record.title,
                existing["start_date"] != self._date_to_text(record.start_date),
                existing["end_date"] != self._date_to_text(record.end_date),
                existing["location"] != record.location,
                existing["files_url"] != record.files_url,
                existing["portal_url"] != record.portal_url,
            ))

            if changed:
                cursor.execute(
                    """
                    UPDATE meetings
                       SET working_group = ?,
                           subgroup = ?,
                           short_name = ?,
                           title = ?,
                           start_date = ?,
                           end_date = ?,
                           location = ?,
                           files_url = ?,
                           portal_url = ?,
                           last_synced = ?,
                           updated_at = ?
                     WHERE meeting_id = ?
                    """,
                    (
                        record.working_group.value,
                        record.subgroup,
                        record.short_name,
                        record.title,
                        self._date_to_text(record.start_date),
                        self._date_to_text(record.end_date),
                        record.location,
                        record.files_url,
                        record.portal_url,
                        record.last_synced.isoformat(),
                        now,
                        record.meeting_id,
                    ),
                )
                self.connection.commit()
                return False, True

            cursor.execute(
                "UPDATE meetings SET last_synced = ?, updated_at = ? WHERE meeting_id = ?",
                (record.last_synced.isoformat(), now, record.meeting_id),
            )
            self.connection.commit()
            return False, False

    def bulk_upsert_meetings(self, meetings: Iterable[MeetingMetadata]) -> tuple[int, int]:
        inserted = 0
        updated = 0
        for meeting in meetings:
            created, changed = self.upsert_meeting(meeting)
            if created:
                inserted += 1
            elif changed:
                updated += 1
        return inserted, updated

    def query_meetings(self, config: MeetingQueryConfig) -> list[MeetingMetadata]:
        clauses: list[str] = []
        params: list[Any] = []

        if config.working_groups:
            placeholders = ",".join(["?"] * len(config.working_groups))
            clauses.append(f"working_group IN ({placeholders})")
            params.extend([wg.value for wg in config.working_groups])

        if not config.include_without_files:
            clauses.append("files_url IS NOT NULL AND files_url != ''")

        query_parts = ["SELECT * FROM meetings"]
        if clauses:
            query_parts.append("WHERE " + " AND ".join(clauses))

        if config.order == SortOrder.ASC:
            query_parts.append("ORDER BY start_date ASC, meeting_id ASC")
        else:
            query_parts.append("ORDER BY start_date DESC, meeting_id DESC")

        if config.limit is not None:
            query_parts.append("LIMIT ?")
            params.append(config.limit)

        query = " ".join(query_parts)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_meeting_metadata(row) for row in rows]

    def upsert_tdoc(self, metadata: TDocMetadata) -> tuple[bool, bool]:
        record = TDocRecord.from_metadata(metadata)
        now = datetime.now(UTC).isoformat()

        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM tdocs WHERE tdoc_id = ?",
                (record.tdoc_id,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.execute(
                    """
                    INSERT INTO tdocs (
                        tdoc_id, url, working_group, subgroup, meeting, meeting_id,
                        file_size, document_type, checksum, source_path, date_created,
                        date_retrieved, date_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.tdoc_id,
                        record.url,
                        record.working_group.value,
                        record.subgroup,
                        record.meeting,
                        record.meeting_id,
                        record.file_size,
                        record.document_type,
                        record.checksum,
                        record.source_path,
                        self._datetime_to_text(record.date_created),
                        record.date_retrieved.isoformat(),
                        now,
                    ),
                )
                self.connection.commit()
                return True, False

            new_date_created = self._datetime_to_text(record.date_created)
            new_date_retrieved = record.date_retrieved.isoformat()
            changed = any((
                existing["url"] != record.url,
                existing["working_group"] != record.working_group.value,
                existing["subgroup"] != record.subgroup,
                existing["meeting"] != record.meeting,
                existing["meeting_id"] != record.meeting_id,
                existing["file_size"] != record.file_size,
                existing["document_type"] != record.document_type,
                existing["checksum"] != record.checksum,
                existing["source_path"] != record.source_path,
                existing["date_created"] != new_date_created,
                existing["date_retrieved"] != new_date_retrieved,
            ))

            if changed:
                cursor.execute(
                    """
                    UPDATE tdocs
                       SET url = ?,
                           working_group = ?,
                           subgroup = ?,
                           meeting = ?,
                           meeting_id = ?,
                           file_size = ?,
                           document_type = ?,
                           checksum = ?,
                           source_path = ?,
                           date_created = ?,
                           date_retrieved = ?,
                           date_updated = ?
                     WHERE tdoc_id = ?
                    """,
                    (
                        record.url,
                        record.working_group.value,
                        record.subgroup,
                        record.meeting,
                        record.meeting_id,
                        record.file_size,
                        record.document_type,
                        record.checksum,
                        record.source_path,
                        new_date_created,
                        new_date_retrieved,
                        now,
                        record.tdoc_id,
                    ),
                )
                self.connection.commit()
                return False, True

            cursor.execute(
                "UPDATE tdocs SET date_updated = ? WHERE tdoc_id = ?",
                (now, record.tdoc_id),
            )
            self.connection.commit()
            return False, False

    def bulk_upsert_tdocs(self, tdocs: Iterable[TDocMetadata]) -> tuple[int, int]:
        inserted = 0
        updated = 0
        for metadata in tdocs:
            created, changed = self.upsert_tdoc(metadata)
            if created:
                inserted += 1
            elif changed:
                updated += 1
        return inserted, updated

    def get_existing_tdoc_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[str]:
        params: list[Any] = []
        query = "SELECT tdoc_id FROM tdocs"

        if working_groups:
            working_groups_list = [wg.value for wg in working_groups]
            placeholders = ["?"] * len(working_groups_list)
            query += f" WHERE working_group IN ({','.join(placeholders)})"
            params.extend(working_groups_list)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return {str(row["tdoc_id"]).upper() for row in rows}

    def query_tdocs(self, config: QueryConfig) -> list[TDocMetadata]:
        clauses: list[str] = []
        params: list[Any] = []

        if config.tdoc_ids:
            placeholders = ",".join(["?"] * len(config.tdoc_ids))
            clauses.append(f"tdoc_id IN ({placeholders})")
            params.extend(config.tdoc_ids)

        if config.working_groups:
            placeholders = ",".join(["?"] * len(config.working_groups))
            clauses.append(f"working_group IN ({placeholders})")
            params.extend([wg.value for wg in config.working_groups])

        if config.start_date is not None:
            clauses.append("date_retrieved >= ?")
            params.append(config.start_date.isoformat())

        if config.end_date is not None:
            clauses.append("date_retrieved <= ?")
            params.append(config.end_date.isoformat())

        query_parts = ["SELECT * FROM tdocs"]
        if clauses:
            query_parts.append("WHERE " + " AND ".join(clauses))

        if config.order == SortOrder.ASC:
            query_parts.append("ORDER BY date_retrieved ASC, tdoc_id ASC")
        else:
            query_parts.append("ORDER BY date_retrieved DESC, tdoc_id DESC")

        if config.limit is not None:
            query_parts.append("LIMIT ?")
            params.append(config.limit)

        query = " ".join(query_parts)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_tdoc_metadata(row) for row in rows]

    def get_existing_meeting_ids(self, working_groups: Iterable[WorkingGroup] | None = None) -> set[int]:
        query = "SELECT meeting_id FROM meetings"
        params: list[Any] = []

        if working_groups:
            working_groups_list = [wg.value for wg in working_groups]
            placeholders = ["?"] * len(working_groups_list)
            query += f" WHERE working_group IN ({','.join(placeholders)})"
            params.extend(working_groups_list)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return {int(row["meeting_id"]) for row in rows}

    def get_statistics(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM tdocs")
            stats["total_tdocs"] = int(cursor.fetchone()["total"])

            cursor.execute("SELECT working_group, COUNT(*) AS cnt FROM tdocs GROUP BY working_group")
            stats["by_working_group"] = {row["working_group"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT COUNT(*) AS recent
                  FROM tdocs
                 WHERE date_retrieved >= datetime('now', '-1 day')
                """
            )
            stats["last_24_hours"] = int(cursor.fetchone()["recent"])

            cursor.execute("SELECT MIN(date_retrieved) AS first, MAX(date_retrieved) AS last FROM tdocs")
            row = cursor.fetchone()
            stats["date_first"] = row["first"]
            stats["date_last"] = row["last"]

            cursor.execute("SELECT COUNT(DISTINCT document_type) AS types FROM tdocs WHERE document_type IS NOT NULL")
            stats["unique_document_types"] = int(cursor.fetchone()["types"])

        return stats

    @staticmethod
    def _row_to_tdoc_metadata(row: sqlite3.Row) -> TDocMetadata:
        try:
            return TDocMetadata(
                tdoc_id=row["tdoc_id"],
                url=row["url"],
                working_group=WorkingGroup(row["working_group"]),
                subgroup=row["subgroup"],
                meeting=row["meeting"],
                meeting_id=row["meeting_id"],
                file_size=row["file_size"],
                document_type=row["document_type"],
                checksum=row["checksum"],
                source_path=row["source_path"],
                date_created=TDocDatabase._text_to_datetime(row["date_created"]),
                date_retrieved=TDocDatabase._text_to_datetime_required(row["date_retrieved"]),
            )
        except (ValueError, ValidationError) as exc:
            raise DatabaseError.parse_failure("tdoc", f"{row['tdoc_id']}|{exc}") from exc

    @staticmethod
    def _row_to_meeting_metadata(row: sqlite3.Row) -> MeetingMetadata:
        try:
            return MeetingMetadata(
                meeting_id=row["meeting_id"],
                working_group=WorkingGroup(row["working_group"]),
                subgroup=row["subgroup"],
                short_name=row["short_name"],
                title=row["title"],
                start_date=TDocDatabase._text_to_date(row["start_date"]),
                end_date=TDocDatabase._text_to_date(row["end_date"]),
                location=row["location"],
                files_url=row["files_url"],
                portal_url=row["portal_url"],
            )
        except (ValueError, ValidationError) as exc:
            raise DatabaseError.parse_failure("meeting", f"{row['meeting_id']}|{exc}") from exc

    @staticmethod
    def _date_to_text(value: date | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _datetime_to_text(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _text_to_datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None

    @staticmethod
    def _text_to_datetime_required(value: str | None) -> datetime:
        dt_value = TDocDatabase._text_to_datetime(value)
        if dt_value is None:
            raise DatabaseError.missing_datetime()
        return dt_value

    @staticmethod
    def _text_to_date(value: str | None) -> date | None:
        return date.fromisoformat(value) if value is not None else None


if __name__ == "__main__":
    pass
# end of file
