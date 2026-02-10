"""Database facade exports."""

from __future__ import annotations

import logging

from tdoc_crawler.database.connection import TDocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.utils.normalization import normalize_portal_meeting_name

logger = logging.getLogger(__name__)


__all__ = [
    "DatabaseError",
    "TDocDatabase",
    "resolve_meeting_id",
]


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
    # Query all meetings from database
    from tdoc_crawler.models import MeetingQueryConfig, SortOrder

    config = MeetingQueryConfig(
        cache_dir=database.db_file.parent,
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
