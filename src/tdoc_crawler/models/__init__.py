"""Core data models and configuration primitives used across the CLI.

NOTE: Domain models (TDocMetadata, MeetingMetadata, etc.) should be imported
directly from their source modules:
- tdoc_crawler.tdocs.models (TDocMetadata, TDocCrawlConfig, QueryConfig)
- tdoc_crawler.meetings.models (MeetingMetadata, MeetingCrawlConfig, MeetingQueryConfig)
"""

from __future__ import annotations

from .base import (
    OutputFormat,
    PortalCredentials,
    SortOrder,
)
from .crawl_log import CrawlLogEntry
from .subworking_groups import (
    CODE_INDEX,
    SUBTB_INDEX,
    SUBWORKING_GROUP_RECORDS,
    SubWorkingGroupRecord,
)
from .working_groups import (
    WORKING_GROUP_RECORDS,
    WorkingGroup,
    WorkingGroupRecord,
)

__all__ = [
    "CODE_INDEX",
    "SUBTB_INDEX",
    "SUBWORKING_GROUP_RECORDS",
    "WORKING_GROUP_RECORDS",
    "CrawlLogEntry",
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
    "SubWorkingGroupRecord",
    "WorkingGroup",
    "WorkingGroupRecord",
]
