"""Meeting domain package."""

from __future__ import annotations

from tdoc_crawler.meetings.operations import MeetingCrawler, MeetingCrawlResult
from tdoc_crawler.meetings.utils import normalize_subgroup_alias, normalize_working_group_alias

__all__ = [
    "MeetingCrawlResult",
    "MeetingCrawler",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
]
