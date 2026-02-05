"""Crawlers for retrieving TDoc and meeting metadata from 3GPP resources."""

from __future__ import annotations

from .constants import (
    EXCLUDED_DIRS,
    EXCLUDED_DIRS_NORMALIZED,
    MEETING_CODE_REGISTRY,
    TDOC_DOWNLOAD_URL,
    TDOC_PATTERN,
    TDOC_PATTERN_STR,
    TDOC_SUBDIRS,
    TDOC_SUBDIRS_NORMALIZED,
)
from .hybrid import HybridCrawlResult, HybridTDocCrawler
from .meeting_doclist import (
    DocumentListError,
    convert_excel_row_to_tdoc_metadata,
    fetch_meeting_document_list,
    parse_excel_document_list,
)
from .meetings import (
    MeetingCrawler,
    MeetingCrawlResult,
    normalize_subgroup_alias,
    normalize_working_group_alias,
)
from .parallel import fetch_meeting_tdocs
from .portal import (
    PortalAuthenticationError,
    PortalParsingError,
    PortalSession,
    extract_tdoc_url_from_portal,
    fetch_tdoc_metadata,
    parse_tdoc_portal_page,
)
from .tdocs import TDocCrawler, TDocCrawlResult
from .whatthespec import WhatTheSpecResolutionError, resolve_via_whatthespec

__all__ = [
    "EXCLUDED_DIRS",
    "EXCLUDED_DIRS_NORMALIZED",
    "MEETING_CODE_REGISTRY",
    "TDOC_DOWNLOAD_URL",
    "TDOC_PATTERN",
    "TDOC_PATTERN_STR",
    "TDOC_SUBDIRS",
    "TDOC_SUBDIRS_NORMALIZED",
    "DocumentListError",
    "HybridCrawlResult",
    "HybridTDocCrawler",
    "MeetingCrawlResult",
    "MeetingCrawler",
    "PortalAuthenticationError",
    "PortalParsingError",
    "PortalSession",
    "TDocCrawlResult",
    "TDocCrawler",
    "WhatTheSpecResolutionError",
    "convert_excel_row_to_tdoc_metadata",
    "extract_tdoc_url_from_portal",
    "fetch_meeting_document_list",
    "fetch_meeting_tdocs",
    "fetch_tdoc_metadata",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
    "parse_excel_document_list",
    "parse_tdoc_portal_page",
    "resolve_via_whatthespec",
]
