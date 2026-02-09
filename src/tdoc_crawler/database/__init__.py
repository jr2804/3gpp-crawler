"""Database facade exports."""

from __future__ import annotations

import logging
from pathlib import Path

from tdoc_crawler.database.connection import TDocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.models import MeetingMetadata, MeetingQueryConfig, SortOrder

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"


def database_path(cache_dir: Path) -> Path:
    """Get database path from cache directory.

    Args:
        cache_dir: Cache directory for database storage.

    Returns:
        Path to database file (cache_dir/tdoc_crawler.db).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / DEFAULT_DATABASE_FILENAME


def resolve_meeting_id(database: TDocDatabase, meeting_name: str) -> int | None:
    """Resolve meeting name to meeting_id from database.

    Uses fuzzy matching to handle variations in meeting names:
    - Exact match (case-insensitive)
    - Normalized name match
    - Prefix/suffix matching for variations like "SA4-e" vs "3GPPSA4-e"

    Args:
        database: Database connection
        meeting_name: Meeting identifier (e.g., "SA4#133-e" or "S4-133-e")

    Returns:
        Meeting ID if found, None otherwise
    """
    # Local import to avoid circular import
    from tdoc_crawler.specs.normalization import normalize_portal_meeting_name

    # Query all meetings from database
    config = MeetingQueryConfig(
        cache_dir=database.db_path.parent,
        working_groups=None,
        subgroups=None,
        limit=None,
        order=SortOrder.DESC,
        include_without_files=True,
    )
    all_meetings = database.query_meetings(config)

    def _match_name(candidate: str, cached: str | None) -> bool:
        """Check if candidate matches cached name via fuzzy matching."""
        if not cached:
            return False
        candidate_lower = candidate.lower()
        cached_lower = cached.lower()

        # Exact match
        if candidate_lower == cached_lower:
            return True
        # Candidate is prefix/suffix of cached or vice versa
        return (
            cached_lower.startswith(candidate_lower)
            or cached_lower.endswith(candidate_lower)
            or candidate_lower.startswith(cached_lower)
            or candidate_lower.endswith(cached_lower)
        )

    # Try matches with original and normalized names
    normalized = normalize_portal_meeting_name(meeting_name)

    candidates = [meeting_name]
    if normalized != meeting_name:
        candidates.append(normalized)

    for candidate in candidates:
        for meeting in all_meetings:
            if _match_name(candidate, meeting.short_name):
                return meeting.meeting_id

    return None


__all__ = ["DEFAULT_DATABASE_FILENAME", "DatabaseError", "MeetingMetadata", "TDocDatabase", "database_path", "resolve_meeting_id"]
