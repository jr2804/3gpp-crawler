"""Misc. helper functions for CLI operations."""

from __future__ import annotations

from datetime import UTC, datetime

from tdoc_crawler.logging import get_logger

_logger = get_logger(__name__)


def utc_now() -> datetime:
    """Return the current UTC timestamp as an aware datetime."""
    return datetime.now(UTC)
