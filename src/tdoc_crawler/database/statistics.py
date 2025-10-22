"""Database statistics and reporting."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class DatabaseStatistics:
    """Database statistics summary."""

    total_tdocs: int
    validated_tdocs: int
    invalid_tdocs: int
    total_meetings: int
    total_working_groups: int
    working_group_breakdown: dict[str, int]
    recent_crawls: list[dict[str, str | int]]


def get_statistics(conn: sqlite3.Connection) -> DatabaseStatistics:
    """Get comprehensive database statistics.

    Args:
        conn: Database connection

    Returns:
        DatabaseStatistics with aggregated counts and breakdowns
    """
    cursor = conn.cursor()

    try:
        # Total TDocs
        cursor.execute("SELECT COUNT(*) FROM tdocs")
        total_tdocs = cursor.fetchone()[0]

        # Validated TDocs
        cursor.execute("SELECT COUNT(*) FROM tdocs WHERE validated = 1")
        validated_tdocs = cursor.fetchone()[0]

        # Invalid TDocs
        cursor.execute("SELECT COUNT(*) FROM tdocs WHERE validation_failed = 1")
        invalid_tdocs = cursor.fetchone()[0]

        # Total meetings
        cursor.execute("SELECT COUNT(*) FROM meetings")
        total_meetings = cursor.fetchone()[0]

        # Total working groups
        cursor.execute("SELECT COUNT(DISTINCT tbid) FROM working_groups")
        total_working_groups = cursor.fetchone()[0]

        # Breakdown by working group
        cursor.execute(
            """
            SELECT working_group, COUNT(*) as count
            FROM tdocs
            GROUP BY working_group
            ORDER BY count DESC
            """
        )
        working_group_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # Recent crawls (last 10)
        cursor.execute(
            """
            SELECT
                crawl_type,
                start_time,
                end_time,
                working_groups,
                items_added,
                items_updated,
                errors_count,
                status
            FROM crawl_log
            ORDER BY start_time DESC
            LIMIT 10
            """
        )
        recent_crawls = [
            {
                "crawl_type": row[0],
                "start_time": row[1],
                "end_time": row[2],
                "working_groups": row[3],
                "items_added": row[4],
                "items_updated": row[5],
                "errors_count": row[6],
                "status": row[7],
            }
            for row in cursor.fetchall()
        ]

        return DatabaseStatistics(
            total_tdocs=total_tdocs,
            validated_tdocs=validated_tdocs,
            invalid_tdocs=invalid_tdocs,
            total_meetings=total_meetings,
            total_working_groups=total_working_groups,
            working_group_breakdown=working_group_breakdown,
            recent_crawls=recent_crawls,
        )

    finally:
        cursor.close()
