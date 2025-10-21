"""Crawlers for retrieving TDoc and meeting metadata from 3GPP resources."""

from __future__ import annotations

# Re-export all public symbols
from .meetings import (
    MEETING_CODE_REGISTRY,
    MeetingCrawler,
    MeetingCrawlResult,
    normalize_subgroup_alias,
    normalize_working_group_alias,
)
from .tdocs import EXCLUDED_DIRS, TDOC_PATTERN, TDocCrawler, TDocCrawlResult

__all__ = [
    "EXCLUDED_DIRS",
    "MEETING_CODE_REGISTRY",
    "MeetingCrawler",
    "MeetingCrawlResult",
    "TDOC_PATTERN",
    "TDocCrawler",
    "TDocCrawlResult",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
]
