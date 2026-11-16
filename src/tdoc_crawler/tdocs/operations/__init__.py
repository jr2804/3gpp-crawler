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
    get_meeting_checkout_folder,
    prepare_tdoc_file,
    prepare_tdoc_selection,
)
from tdoc_crawler.tdocs.operations.crawl import (
    MeetingPatternError,
    TDocCrawler,
    TDocCrawlResult,
    filter_meetings_by_patterns,
)
from tdoc_crawler.tdocs.operations.fetch import (
    FetchMethod,
    FetchMissingResult,
    create_source,
    fetch_missing_tdocs,
    fetch_missing_tdocs_batch,
    # fetch_tdoc,
    fetch_via_portal_url_batch,
    fetch_via_whatthespec_batch,
)
from tdoc_crawler.tdocs.operations.main_file import (
    has_revision_marks,
    member_candidates,
    resolve_main_file,
    select_heuristic_main_file,
)
from tdoc_crawler.tdocs.operations.open import (
    TDocNotFoundError,
    TDocOpenResult,
    resolve_tdoc_main_file,
)
from tdoc_crawler.tdocs.operations.reclassify import ReclassifyOutcome, reclassify_tdocs

__all__ = [
    "CheckoutResult",
    "FetchMethod",
    "FetchMissingResult",
    "MeetingPatternError",
    "ReclassifyOutcome",
    "TDocCrawlResult",
    "TDocCrawler",
    "TDocNotFoundError",
    "TDocOpenResult",
    "checkout_meeting_tdocs",
    "checkout_tdoc",
    "checkout_tdocs",
    "clear_checkout_tdocs",
    "create_source",
    "fetch_missing_tdocs",
    "fetch_missing_tdocs_batch",
    "fetch_via_portal_url_batch",
    "fetch_via_whatthespec_batch",
    "filter_meetings_by_patterns",
    "get_checked_out_tdocs",
    "get_checkout_path",
    "get_meeting_checkout_folder",
    "has_revision_marks",
    "member_candidates",
    "prepare_tdoc_file",
    "prepare_tdoc_selection",
    "reclassify_tdocs",
    "resolve_main_file",
    "resolve_tdoc_main_file",
    "select_heuristic_main_file",
]
