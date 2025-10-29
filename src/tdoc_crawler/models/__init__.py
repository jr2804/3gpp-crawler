"""Core data models and configuration primitives used across the CLI."""

from __future__ import annotations

# Re-export all public symbols
from .base import (
    DEFAULT_CACHE_DIR,
    BaseConfigModel,
    HttpCacheConfig,
    OutputFormat,
    PortalCredentials,
    SortOrder,
    utc_now,
)
from .crawl_limits import CrawlLimits
from .crawl_log import CrawlLogEntry
from .meetings import MeetingCrawlConfig, MeetingMetadata, MeetingQueryConfig
from .subworking_groups import (
    CODE_INDEX,
    SUBTB_INDEX,
    SUBWORKING_GROUP_RECORDS,
    SubWorkingGroupRecord,
)
from .tdocs import CrawlConfig, QueryConfig, TDocCrawlConfig, TDocMetadata
from .working_groups import WORKING_GROUP_RECORDS, WorkingGroup, WorkingGroupRecord

__all__ = sorted([
    "BaseConfigModel",
    "CODE_INDEX",
    "CrawlConfig",
    "CrawlLimits",
    "CrawlLogEntry",
    "DEFAULT_CACHE_DIR",
    "HttpCacheConfig",
    "MeetingCrawlConfig",
    "MeetingMetadata",
    "MeetingQueryConfig",
    "OutputFormat",
    "PortalCredentials",
    "QueryConfig",
    "SortOrder",
    "SUBTB_INDEX",
    "SUBWORKING_GROUP_RECORDS",
    "SubWorkingGroupRecord",
    "TDocCrawlConfig",
    "TDocMetadata",
    "WORKING_GROUP_RECORDS",
    "WorkingGroup",
    "WorkingGroupRecord",
    "utc_now",
])
