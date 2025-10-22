"""Database layer for TDoc metadata storage and retrieval.

This submodule provides organized database operations:
- connection: TDocDatabase context manager
- errors: DatabaseError exception
- schema: Database initialization
- converters: Date/datetime utilities
- logging: Crawl operation tracking
- meetings: Meeting CRUD operations
- tdocs: TDoc CRUD operations
- statistics: Database statistics and reporting
"""

from tdoc_crawler.database.connection import TDocDatabase
from tdoc_crawler.database.converters import (
    date_to_text,
    datetime_to_text,
    text_to_date,
    text_to_datetime,
    text_to_datetime_required,
)
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.logging import log_crawl_end, log_crawl_start
from tdoc_crawler.database.meetings import (
    bulk_upsert_meetings,
    get_existing_meeting_ids,
    get_subgroup_by_code,
    query_meetings,
    row_to_meeting_metadata,
    upsert_meeting,
)
from tdoc_crawler.database.schema import configure_connection, initialize_schema
from tdoc_crawler.database.statistics import DatabaseStatistics, get_statistics
from tdoc_crawler.database.tdocs import (
    bulk_upsert_tdocs,
    cache_invalid_tdoc,
    get_cached_invalid_tdocs,
    get_existing_tdoc_ids,
    get_processed_meetings,
    query_tdocs,
    row_to_tdoc_metadata,
    upsert_tdoc,
)

__all__ = [
    # Connection manager
    "TDocDatabase",
    # Exceptions
    "DatabaseError",
    # Schema initialization
    "configure_connection",
    "initialize_schema",
    # Converters
    "date_to_text",
    "datetime_to_text",
    "text_to_date",
    "text_to_datetime",
    "text_to_datetime_required",
    # Crawl logging
    "log_crawl_start",
    "log_crawl_end",
    # Meeting operations
    "upsert_meeting",
    "bulk_upsert_meetings",
    "query_meetings",
    "get_existing_meeting_ids",
    "get_subgroup_by_code",
    "row_to_meeting_metadata",
    # TDoc operations
    "upsert_tdoc",
    "bulk_upsert_tdocs",
    "query_tdocs",
    "get_existing_tdoc_ids",
    "get_processed_meetings",
    "cache_invalid_tdoc",
    "get_cached_invalid_tdocs",
    "row_to_tdoc_metadata",
    # Statistics
    "DatabaseStatistics",
    "get_statistics",
]
