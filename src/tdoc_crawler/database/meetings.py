"""Meeting-related database operations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from tdoc_crawler.database.converters import date_to_text, text_to_date
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.models import (
    MeetingMetadata,
    MeetingQueryConfig,
    MeetingRecord,
    SortOrder,
    WorkingGroup,
)


def upsert_meeting(conn: sqlite3.Connection, meeting: MeetingMetadata) -> tuple[bool, bool]:
    """Insert or update a meeting record.

    Args:
        conn: Database connection
        meeting: Meeting metadata to upsert

    Returns:
        Tuple of (created, updated) booleans
    """
    record = MeetingRecord.from_metadata(meeting)
    now = datetime.now(UTC).isoformat()

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM meetings WHERE meeting_id = ?",
            (record.meeting_id,),
        )
        existing = cursor.fetchone()

        if existing is None:
            cursor.execute(
                """
                INSERT INTO meetings (
                    meeting_id, tbid, subtb, short_name, title, start_date, end_date,
                    location, files_url, portal_url, last_synced, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.meeting_id,
                    record.tbid,
                    record.subtb,
                    record.short_name,
                    record.title,
                    date_to_text(record.start_date),
                    date_to_text(record.end_date),
                    record.location,
                    record.files_url,
                    record.portal_url,
                    record.last_synced.isoformat(),
                    now,
                    now,
                ),
            )
            conn.commit()
            return True, False

        changed = any((
            existing["tbid"] != record.tbid,
            existing["subtb"] != record.subtb,
            existing["short_name"] != record.short_name,
            existing["title"] != record.title,
            existing["start_date"] != date_to_text(record.start_date),
            existing["end_date"] != date_to_text(record.end_date),
            existing["location"] != record.location,
            existing["files_url"] != record.files_url,
            existing["portal_url"] != record.portal_url,
        ))

        if changed:
            cursor.execute(
                """
                UPDATE meetings
                   SET tbid = ?,
                       subtb = ?,
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
                    record.tbid,
                    record.subtb,
                    record.short_name,
                    record.title,
                    date_to_text(record.start_date),
                    date_to_text(record.end_date),
                    record.location,
                    record.files_url,
                    record.portal_url,
                    record.last_synced.isoformat(),
                    now,
                    record.meeting_id,
                ),
            )
            conn.commit()
            return False, True

        cursor.execute(
            "UPDATE meetings SET last_synced = ?, updated_at = ? WHERE meeting_id = ?",
            (record.last_synced.isoformat(), now, record.meeting_id),
        )
        conn.commit()
        return False, False
    finally:
        cursor.close()


def bulk_upsert_meetings(conn: sqlite3.Connection, meetings: Iterable[MeetingMetadata]) -> tuple[int, int]:
    """Bulk insert or update meeting records.

    Args:
        conn: Database connection
        meetings: Iterable of meeting metadata

    Returns:
        Tuple of (inserted_count, updated_count)
    """
    inserted = 0
    updated = 0
    for meeting in meetings:
        created, changed = upsert_meeting(conn, meeting)
        if created:
            inserted += 1
        elif changed:
            updated += 1
    return inserted, updated


def query_meetings(conn: sqlite3.Connection, config: MeetingQueryConfig) -> list[MeetingMetadata]:
    """Query meetings with filters and sorting.

    Args:
        conn: Database connection
        config: Query configuration with filters

    Returns:
        List of matching meeting metadata
    """
    clauses: list[str] = []
    params: list[Any] = []

    if config.working_groups:
        placeholders = ",".join(["?"] * len(config.working_groups))
        clauses.append(f"wg.tbid IN ({placeholders})")
        params.extend([wg.tbid for wg in config.working_groups])

    if config.subgroups:
        placeholders = ",".join(["?"] * len(config.subgroups))
        clauses.append(f"UPPER(swg.code) IN ({placeholders})")
        params.extend([sg.upper() for sg in config.subgroups])

    if not config.include_without_files:
        clauses.append("m.files_url IS NOT NULL AND m.files_url != ''")

    query_parts = [
        """
        SELECT m.*, wg.code as wg_code, swg.code as swg_code
        FROM meetings m
        INNER JOIN working_groups wg ON m.tbid = wg.tbid
        LEFT JOIN subworking_groups swg ON m.subtb = swg.subtb
        """
    ]

    if clauses:
        query_parts.append("WHERE " + " AND ".join(clauses))

    if config.order == SortOrder.ASC:
        query_parts.append("ORDER BY m.start_date ASC, m.meeting_id ASC")
    else:
        query_parts.append("ORDER BY m.start_date DESC, m.meeting_id DESC")

    if config.limit is not None:
        query_parts.append("LIMIT ?")
        params.append(config.limit)

    query = " ".join(query_parts)

    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    return [row_to_meeting_metadata(row) for row in rows]


def get_existing_meeting_ids(conn: sqlite3.Connection, working_groups: Iterable[WorkingGroup] | None = None) -> set[int]:
    """Get all existing meeting IDs, optionally filtered by working groups.

    Args:
        conn: Database connection
        working_groups: Optional filter by working groups

    Returns:
        Set of meeting IDs
    """
    query = "SELECT meeting_id FROM meetings"
    params: list[Any] = []

    if working_groups:
        working_groups_list = [wg.tbid for wg in working_groups]
        placeholders = ["?"] * len(working_groups_list)
        query += f" WHERE tbid IN ({','.join(placeholders)})"
        params.extend(working_groups_list)

    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    return {int(row["meeting_id"]) for row in rows}


def get_subgroup_by_code(conn: sqlite3.Connection, code: str) -> dict[str, Any] | None:
    """Look up a subworking group by its code.

    Args:
        conn: Database connection
        code: The subgroup code (e.g., 'S4', 'R1', 'CP')

    Returns:
        Dictionary with subgroup data or None if not found
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT subtb, tbid, code, name FROM subworking_groups WHERE code = ?",
            (code.upper(),),
        )
        row = cursor.fetchone()
    finally:
        cursor.close()

    if row is None:
        return None

    return {
        "subtb": row["subtb"],
        "tbid": row["tbid"],
        "code": row["code"],
        "name": row["name"],
    }


def row_to_meeting_metadata(row: sqlite3.Row) -> MeetingMetadata:
    """Convert database row to MeetingMetadata model.

    Args:
        row: SQLite row from meetings query

    Returns:
        MeetingMetadata instance

    Raises:
        DatabaseError: If row cannot be parsed
    """
    try:
        wg_code = row["wg_code"]
        working_group = WorkingGroup(wg_code)

        try:
            subgroup = row["swg_code"]
        except (KeyError, IndexError):
            subgroup = None

        return MeetingMetadata(
            meeting_id=row["meeting_id"],
            tbid=row["tbid"],
            subtb=row["subtb"],
            working_group=working_group,
            subgroup=subgroup,
            short_name=row["short_name"],
            title=row["title"],
            start_date=text_to_date(row["start_date"]),
            end_date=text_to_date(row["end_date"]),
            location=row["location"],
            files_url=row["files_url"],
            portal_url=row["portal_url"],
        )
    except (ValueError, ValidationError) as exc:
        raise DatabaseError.parse_failure("meeting", f"{row['meeting_id']}|{exc}") from exc
