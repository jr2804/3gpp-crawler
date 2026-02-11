"""Core data models and configuration primitives used across the CLI.

NOTE: Domain models (TDocMetadata, MeetingMetadata, etc.) should be imported
directly from their source modules:
- tdoc_crawler.tdocs.models (TDocMetadata, TDocCrawlConfig, QueryConfig)
- tdoc_crawler.meetings.models (MeetingMetadata, MeetingCrawlConfig, MeetingQueryConfig)
"""

from __future__ import annotations

from .base import (
    BaseConfigModel,
    HttpCacheConfig,
    OutputFormat,
    PortalCredentials,
    SortOrder,
)
from .crawl_limits import CrawlLimits
from .crawl_log import CrawlLogEntry

# Note: Specification models have been moved to tdoc_crawler.specs.models
# Import from there directly to avoid circular dependencies
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
    "CrawlLimits",
    "CrawlLogEntry",
    "HttpCacheConfig",
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
    "SpecQueryFilters",
    "SpecQueryResult",
    "Specification",
    "SpecificationDownload",
    "SpecificationSourceRecord",
    "SpecificationVersion",
    "SubWorkingGroupRecord",
    "SUBTB_INDEX",
    "SUBWORKING_GROUP_RECORDS",
    "WorkingGroup",
    "WorkingGroupRecord",
    "WORKING_GROUP_RECORDS",
]
