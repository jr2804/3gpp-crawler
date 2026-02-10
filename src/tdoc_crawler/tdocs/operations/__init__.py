"""TDoc operations."""

from __future__ import annotations

from tdoc_crawler.tdocs.operations.checkout import (
    CheckoutResult,
    checkout_meeting_tdocs,
    checkout_tdoc,
    checkout_tdocs,
    clear_checkout_tdocs,
    get_checked_out_tdocs,
    get_checkout_path,
    prepare_tdoc_file,
)
from tdoc_crawler.tdocs.operations.crawl import (
    HybridCrawlResult,
    HybridTDocCrawler,
    TDocCrawler,
    TDocCrawlResult,
)
from tdoc_crawler.tdocs.operations.fetch import (
    FetchMethod,
    FetchMissingResult,
    create_source,
    create_source_config,
    fetch_missing_tdocs,
    fetch_missing_tdocs_batch,
    fetch_tdoc,
    fetch_via_whatthespec_batch,
)

__all__ = [
    "CheckoutResult",
    "FetchMethod",
    "FetchMissingResult",
    "HybridCrawlResult",
    "HybridTDocCrawler",
    "TDocCrawlResult",
    "TDocCrawler",
    "checkout_meeting_tdocs",
    "checkout_tdoc",
    "checkout_tdocs",
    "clear_checkout_tdocs",
    "create_source",
    "create_source_config",
    "fetch_missing_tdocs",
    "fetch_missing_tdocs_batch",
    "fetch_tdoc",
    "fetch_via_whatthespec_batch",
    "get_checked_out_tdocs",
    "get_checkout_path",
    "prepare_tdoc_file",
]
