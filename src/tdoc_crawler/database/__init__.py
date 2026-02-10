"""Database facade exports."""

from __future__ import annotations

import logging

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase

logger = logging.getLogger(__name__)


__all__ = [
    "DatabaseError",
    "DocDatabase",
    "MeetingDatabase",
    "SpecDatabase",
    "TDocDatabase",
    "resolve_meeting_id",
]


def resolve_meeting_id(database: MeetingDatabase, meeting_name: str) -> int | None:
    """Resolve meeting name to meeting_id from database.

    Uses fuzzy matching to handle variations in meeting names:
    - Exact match (case-insensitive)
    - Normalized name match
    - Prefix/suffix matching for variations like "SA4-e" vs "3GPPSA4-e"

    Args:
        database: Meeting database connection
        meeting_name: Meeting identifier (e.g., "SA4#133-e" or "S4-133-e")

    Returns:
        Meeting ID if found, None otherwise
    """
    return database.resolve_meeting_id(meeting_name)
