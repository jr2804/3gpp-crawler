"""TDoc-related data models and configurations.

DEPRECATED: This module is deprecated. Use tdoc_crawler.tdocs.models instead.

This module now re-exports from the new location for backward compatibility.
All new code should import from tdoc_crawler.tdocs.models.
"""

from __future__ import annotations

# Re-export from new location
from tdoc_crawler.tdocs.models import (
    CrawlConfig,
    QueryConfig,
    TDocCrawlConfig,
    TDocMetadata,
)

__all__ = [
    "CrawlConfig",
    "QueryConfig",
    "TDocCrawlConfig",
    "TDocMetadata",
]
