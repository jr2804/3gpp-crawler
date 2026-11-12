"""Statistics records returned by the database layer.

These are plain dictionaries with a fixed key set, so they are described with
``TypedDict`` instead of the vague ``dict[str, object]``.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class CrawlSummary(TypedDict):
    """One crawl-log entry inside the statistics report."""

    crawl_type: str
    """Type of the crawl operation (e.g. "meeting", "tdoc")."""

    start_time: str
    """ISO timestamp of the crawl start."""

    end_time: str | None
    """ISO timestamp of the crawl end, ``None`` while it is still running."""

    working_groups: str
    """Comma-separated list of the crawled working groups."""

    items_added: int
    """Number of records added by the crawl."""

    items_updated: int
    """Number of records updated by the crawl."""

    errors_count: int
    """Number of errors the crawl ran into."""

    status: str
    """Status of the crawl (e.g. "RUNNING", "COMPLETED")."""


class DatabaseStatistics(TypedDict):
    """Aggregated statistics about the local TDoc database."""

    total_tdocs: int
    """Number of stored TDoc records."""

    validated_tdocs: int
    """Number of TDoc records that validated successfully."""

    invalid_tdocs: int
    """Number of TDoc records that failed validation."""

    total_meetings: int
    """Number of stored meetings."""

    total_working_groups: int
    """Number of known working groups."""

    by_working_group: dict[str, int]
    """TDoc count per working-group code."""

    recent_crawls: list[CrawlSummary]
    """The most recent crawl-log entries."""

    last_24_hours: NotRequired[int]
    """TDoc count of the last 24 hours (only when the source provides it)."""

    date_first: NotRequired[str]
    """Date of the oldest TDoc (only when the source provides it)."""

    date_last: NotRequired[str]
    """Date of the newest TDoc (only when the source provides it)."""

    unique_document_types: NotRequired[int]
    """Number of distinct document types (only when the source provides it)."""


__all__ = [
    "CrawlSummary",
    "DatabaseStatistics",
]
