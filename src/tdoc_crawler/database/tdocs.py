"""TDoc-related database operations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from tdoc_crawler.database.converters import (
    datetime_to_text,
    text_to_datetime,
    text_to_datetime_required,
)
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.models import (
    QueryConfig,
    SortOrder,
    TDocMetadata,
    TDocRecord,
    WorkingGroup,
)


def upsert_tdoc(conn: sqlite3.Connection, metadata: TDocMetadata) -> tuple[bool, bool]:
    """Insert or update a TDoc record.

    Args:
        conn: Database connection
        metadata: TDoc metadata to upsert

    Returns:
        Tuple of (created, updated) booleans
    """
    record = TDocRecord.from_metadata(metadata)
    now = datetime.now(UTC).isoformat()

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM tdocs WHERE tdoc_id = ?",
            (record.tdoc_id,),
        )
        existing = cursor.fetchone()

        if existing is None:
            cursor.execute(
                """
                INSERT INTO tdocs (
                    tdoc_id, url, meeting_id,
                    file_size, title, contact, tdoc_type, for_purpose, agenda_item,
                    status, is_revision_of, document_type, checksum, source_path,
                    date_created, date_retrieved, date_updated, validated, validation_failed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.tdoc_id,
                    record.url,
                    record.meeting_id,
                    record.file_size,
                    record.title,
                    record.contact,
                    record.tdoc_type,
                    record.for_purpose,
                    record.agenda_item,
                    record.status,
                    record.is_revision_of,
                    record.document_type,
                    record.checksum,
                    record.source_path,
                    datetime_to_text(record.date_created),
                    record.date_retrieved.isoformat(),
                    now,
                    1 if record.validated else 0,
                    1 if record.validation_failed else 0,
                ),
            )
            conn.commit()
            return True, False

        new_date_created = datetime_to_text(record.date_created)
        new_date_retrieved = record.date_retrieved.isoformat()
        changed = any((
            existing["url"] != record.url,
            existing["meeting_id"] != record.meeting_id,
            existing["file_size"] != record.file_size,
            existing["title"] != record.title,
            existing["contact"] != record.contact,
            existing["tdoc_type"] != record.tdoc_type,
            existing["for_purpose"] != record.for_purpose,
            existing["agenda_item"] != record.agenda_item,
            existing["status"] != record.status,
            existing["is_revision_of"] != record.is_revision_of,
            existing["document_type"] != record.document_type,
            existing["checksum"] != record.checksum,
            existing["source_path"] != record.source_path,
            existing["date_created"] != new_date_created,
            existing["date_retrieved"] != new_date_retrieved,
            existing["validated"] != (1 if record.validated else 0),
            existing["validation_failed"] != (1 if record.validation_failed else 0),
        ))

        if changed:
            cursor.execute(
                """
                UPDATE tdocs
                   SET url = ?,
                       meeting_id = ?,
                       file_size = ?,
                       title = ?,
                       contact = ?,
                       tdoc_type = ?,
                       for_purpose = ?,
                       agenda_item = ?,
                       status = ?,
                       is_revision_of = ?,
                       document_type = ?,
                       checksum = ?,
                       source_path = ?,
                       date_created = ?,
                       date_retrieved = ?,
                       date_updated = ?,
                       validated = ?,
                       validation_failed = ?
                 WHERE tdoc_id = ?
                """,
                (
                    record.url,
                    record.meeting_id,
                    record.file_size,
                    record.title,
                    record.contact,
                    record.tdoc_type,
                    record.for_purpose,
                    record.agenda_item,
                    record.status,
                    record.is_revision_of,
                    record.document_type,
                    record.checksum,
                    record.source_path,
                    new_date_created,
                    new_date_retrieved,
                    now,
                    1 if record.validated else 0,
                    1 if record.validation_failed else 0,
                    record.tdoc_id,
                ),
            )
            conn.commit()
            return False, True

        cursor.execute(
            "UPDATE tdocs SET date_updated = ? WHERE tdoc_id = ?",
            (now, record.tdoc_id),
        )
        conn.commit()
        return False, False
    finally:
        cursor.close()


def bulk_upsert_tdocs(conn: sqlite3.Connection, tdocs: Iterable[TDocMetadata]) -> tuple[int, int]:
    """Bulk insert or update TDoc records.

    Args:
        conn: Database connection
        tdocs: Iterable of TDoc metadata

    Returns:
        Tuple of (inserted_count, updated_count)
    """
    inserted = 0
    updated = 0
    for metadata in tdocs:
        created, changed = upsert_tdoc(conn, metadata)
        if created:
            inserted += 1
        elif changed:
            updated += 1
    return inserted, updated


def get_existing_tdoc_ids(conn: sqlite3.Connection, working_groups: Iterable[WorkingGroup] | None = None) -> set[str]:
    """Get all existing TDoc IDs, optionally filtered by working groups.

    Args:
        conn: Database connection
        working_groups: Optional filter by working groups

    Returns:
        Set of TDoc IDs (uppercase)
    """
    params: list[Any] = []
    query = "SELECT t.tdoc_id FROM tdocs t"

    if working_groups:
        # Join with meetings to filter by working group
        query += " LEFT JOIN meetings m ON t.meeting_id = m.meeting_id"
        tbids = [wg.tbid for wg in working_groups]
        placeholders = ["?"] * len(tbids)
        query += f" WHERE m.tbid IN ({','.join(placeholders)})"
        params.extend(tbids)

    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    return {str(row["tdoc_id"]).upper() for row in rows}


def query_tdocs(conn: sqlite3.Connection, config: QueryConfig) -> list[TDocMetadata]:
    """Query TDocs with filters and sorting.

    Args:
        conn: Database connection
        config: Query configuration with filters

    Returns:
        List of matching TDoc metadata

    Raises:
        DatabaseError: If query fails
    """
    clauses: list[str] = []
    params: list[Any] = []

    if config.tdoc_ids:
        placeholders = ",".join(["?"] * len(config.tdoc_ids))
        clauses.append(f"tdoc_id IN ({placeholders})")
        params.extend(config.tdoc_ids)

    # Filter by working groups via join to meetings table
    if config.working_groups:
        placeholders = ",".join(["?"] * len(config.working_groups))
        clauses.append(f"m.tbid IN ({placeholders})")
        params.extend([wg.tbid for wg in config.working_groups])

    if config.start_date is not None:
        clauses.append("t.date_retrieved >= ?")
        params.append(config.start_date.isoformat())

    if config.end_date is not None:
        clauses.append("t.date_retrieved <= ?")
        params.append(config.end_date.isoformat())

    # Build query with LEFT JOIN to meetings table
    query_parts = ["SELECT t.* FROM tdocs t LEFT JOIN meetings m ON t.meeting_id = m.meeting_id"]
    if clauses:
        query_parts.append("WHERE " + " AND ".join(clauses))

    if config.order == SortOrder.ASC:
        query_parts.append("ORDER BY t.date_retrieved ASC, t.tdoc_id ASC")
    else:
        query_parts.append("ORDER BY t.date_retrieved DESC, t.tdoc_id DESC")

    if config.limit is not None:
        query_parts.append("LIMIT ?")
        params.append(config.limit)

    query = " ".join(query_parts)

    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as exc:
        raise DatabaseError.parse_failure("tdocs-query", str(exc)) from exc
    finally:
        cursor.close()

    return [row_to_tdoc_metadata(row) for row in rows]


def get_processed_meetings(
    conn: sqlite3.Connection,
    working_groups: Iterable[WorkingGroup] | None = None,
    subgroups: Iterable[str] | None = None,
) -> set[int]:
    """Get meeting IDs that have already been crawled for TDocs.

    Args:
        conn: Database connection
        working_groups: Optional filter by working groups
        subgroups: Optional filter by subgroups

    Returns:
        Set of meeting IDs that have been processed
    """
    query = "SELECT DISTINCT meeting_id FROM tdocs"
    clauses: list[str] = []
    params: list[Any] = []

    if working_groups:
        working_groups_list = [wg.value for wg in working_groups]
        placeholders = ["?"] * len(working_groups_list)
        clauses.append(f"working_group IN ({','.join(placeholders)})")
        params.extend(working_groups_list)

    if subgroups:
        subgroups_list = list(subgroups)
        placeholders = ["?"] * len(subgroups_list)
        clauses.append(f"subgroup IN ({','.join(placeholders)})")
        params.extend(subgroups_list)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    return {int(row["meeting_id"]) for row in rows}


def cache_invalid_tdoc(
    conn: sqlite3.Connection,
    tdoc_id: str,
    url: str,
    working_group: WorkingGroup,
    subgroup: str,
) -> None:
    """Cache a TDoc that failed portal validation.

    Args:
        conn: Database connection
        tdoc_id: The TDoc identifier (case-insensitive)
        url: The FTP/HTTP URL where the file was found
        working_group: The working group this TDoc belongs to
        subgroup: The subgroup identifier
    """
    now = datetime.now(UTC).isoformat()
    tdoc_id_upper = tdoc_id.upper()

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT tdoc_id FROM tdocs WHERE tdoc_id = ?",
            (tdoc_id_upper,),
        )
        if cursor.fetchone() is not None:
            return

        cursor.execute(
            """
            INSERT INTO tdocs (
                tdoc_id, url, working_group, subgroup, meeting, meeting_id,
                file_size, document_type, checksum, source_path,
                date_created, date_retrieved, date_updated,
                validated, validation_failed
            ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?, 0, 1)
            """,
            (
                tdoc_id_upper,
                url,
                working_group.value,
                subgroup,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        cursor.close()


def get_cached_invalid_tdocs(conn: sqlite3.Connection) -> set[str]:
    """Get all TDoc IDs that have been cached as invalid.

    Args:
        conn: Database connection

    Returns:
        Set of TDoc IDs (uppercase) that failed portal validation
    """
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tdoc_id FROM tdocs WHERE validation_failed = 1")
        rows = cursor.fetchall()
    finally:
        cursor.close()

    return {str(row["tdoc_id"]).upper() for row in rows}


def row_to_tdoc_metadata(row: sqlite3.Row) -> TDocMetadata:
    """Convert database row to TDocMetadata model.

    Args:
        row: SQLite row from tdocs query

    Returns:
        TDocMetadata instance

    Raises:
        DatabaseError: If row cannot be parsed
    """
    try:
        return TDocMetadata(
            tdoc_id=row["tdoc_id"],
            url=row["url"],
            meeting_id=row["meeting_id"],
            file_size=row["file_size"],
            title=row["title"],
            contact=row["contact"],
            tdoc_type=row["tdoc_type"],
            for_purpose=row["for_purpose"],
            agenda_item=row["agenda_item"],
            status=row["status"],
            is_revision_of=row["is_revision_of"],
            document_type=row["document_type"],
            checksum=row["checksum"],
            source_path=row["source_path"],
            date_created=text_to_datetime(row["date_created"]),
            date_retrieved=text_to_datetime_required(row["date_retrieved"]),
            validated=bool(row["validated"]) if row["validated"] is not None else False,
            validation_failed=bool(row["validation_failed"]) if row["validation_failed"] is not None else False,
        )
    except (ValueError, ValidationError) as exc:
        raise DatabaseError.parse_failure("tdoc", f"{row['tdoc_id']}|{exc}") from exc
