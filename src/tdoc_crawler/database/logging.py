"""Crawl logging operations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime

from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.models import WorkingGroup


def log_crawl_start(
    conn: sqlite3.Connection,
    crawl_type: str,
    working_groups: Iterable[WorkingGroup],
    incremental: bool,
) -> int:
    """Log the start of a crawl operation.

    Args:
        conn: Database connection
        crawl_type: Type of crawl (e.g., 'tdocs', 'meetings')
        working_groups: Working groups being crawled
        incremental: Whether this is an incremental crawl

    Returns:
        The crawl log ID for tracking this operation

    Raises:
        DatabaseError: If the log entry cannot be created
    """
    now = datetime.now(UTC).isoformat()
    wg_list = ",".join(sorted({wg.value for wg in working_groups}))

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO crawl_log (crawl_type, start_time, working_groups, incremental, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (crawl_type, now, wg_list, int(incremental), "RUNNING"),
        )
        conn.commit()
        crawl_id = cursor.lastrowid
    finally:
        cursor.close()

    if crawl_id is None:
        raise DatabaseError.crawl_log_persist_failed()
    return int(crawl_id)


def log_crawl_end(
    conn: sqlite3.Connection,
    crawl_id: int,
    *,
    items_added: int,
    items_updated: int,
    errors_count: int,
    status: str = "COMPLETED",
) -> None:
    """Log the completion of a crawl operation.

    Args:
        conn: Database connection
        crawl_id: The crawl log ID from log_crawl_start
        items_added: Number of items added during crawl
        items_updated: Number of items updated during crawl
        errors_count: Number of errors encountered
        status: Final status (default: "COMPLETED")
    """
    now = datetime.now(UTC).isoformat()

    cursor = conn.cursor()
    try:
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
        conn.commit()
    finally:
        cursor.close()
