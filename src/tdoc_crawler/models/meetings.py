"""Meeting-related data models and configurations.

DEPRECATED: This module is deprecated. Use tdoc_crawler.meetings.models instead.

This module now re-exports from the new location for backward compatibility.
All new code should import from tdoc_crawler.meetings.models.
"""

from __future__ import annotations

# Re-export from new location
from tdoc_crawler.meetings.models import (
    MeetingCrawlConfig,
    MeetingMetadata,
    MeetingQueryConfig,
)

__all__ = [
    "MeetingCrawlConfig",
    "MeetingMetadata",
    "MeetingQueryConfig",
]
