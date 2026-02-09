"""Crawlers for retrieving TDoc and meeting metadata from 3GPP resources."""

from __future__ import annotations

from tdoc_crawler.crawlers.constants import (
    EXCLUDED_DIRS,
    EXCLUDED_DIRS_NORMALIZED,
    MEETING_CODE_REGISTRY,
    TDOC_DOWNLOAD_URL,
    TDOC_PATTERN,
    TDOC_PATTERN_STR,
    TDOC_SUBDIRS,
    TDOC_SUBDIRS_NORMALIZED,
)
from tdoc_crawler.crawlers.hybrid import HybridCrawlResult, HybridTDocCrawler
from tdoc_crawler.crawlers.meeting_doclist import DocumentListError, convert_excel_row_to_tdoc_metadata, fetch_meeting_document_list, parse_excel_document_list
from tdoc_crawler.crawlers.meetings import MeetingCrawler, MeetingCrawlResult, normalize_subgroup_alias, normalize_working_group_alias
from tdoc_crawler.crawlers.parallel import fetch_meeting_tdocs
from tdoc_crawler.crawlers.portal import (
    PortalAuthenticationError,
    PortalParsingError,
    PortalSession,
    extract_tdoc_url_from_portal,
    fetch_tdoc_metadata,
    parse_tdoc_portal_page,
)
from tdoc_crawler.crawlers.tdocs import TDocCrawler, TDocCrawlResult
from tdoc_crawler.crawlers.whatthespec import WhatTheSpecResolutionError, resolve_via_whatthespec

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
