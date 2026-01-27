"""Core data models and configuration primitives used across the CLI."""

from __future__ import annotations

# Re-export all public symbols
from .base import (  # noqa: F401
    DEFAULT_CACHE_DIR,
    BaseConfigModel,
    OutputFormat,
    PortalCredentials,
    SortOrder,
    utc_now,
)
from .crawl_limits import CrawlLimits  # noqa: F401
from .crawl_log import CrawlLogEntry  # noqa: F401
from .meetings import (  # noqa: F401
    MeetingCrawlConfig,
    MeetingMetadata,
    MeetingQueryConfig,
)
from .subworking_groups import (  # noqa: F401
    CODE_INDEX,
    SUBTB_INDEX,
    SUBWORKING_GROUP_RECORDS,
    SubWorkingGroupRecord,
)
from .tdocs import CrawlConfig, QueryConfig, TDocCrawlConfig, TDocMetadata  # noqa: F401
from .working_groups import (  # noqa: F401
    WORKING_GROUP_RECORDS,
    WorkingGroup,
    WorkingGroupRecord,
)

__all__ = [
    "CODE_INDEX",
    "DEFAULT_CACHE_DIR",
    "SUBTB_INDEX",
    "SUBWORKING_GROUP_RECORDS",
    "WORKING_GROUP_RECORDS",
    "BaseConfigModel",
    "CrawlConfig",
    "CrawlLimits",
    "CrawlLogEntry",
    "MeetingCrawlConfig",
    "MeetingMetadata",
    "MeetingQueryConfig",
    "OutputFormat",
    "PortalCredentials",
    "QueryConfig",
    "SortOrder",
    "SubWorkingGroupRecord",
    "TDocCrawlConfig",
    "TDocMetadata",
    "WorkingGroup",
    "WorkingGroupRecord",
    "utc_now",
]
