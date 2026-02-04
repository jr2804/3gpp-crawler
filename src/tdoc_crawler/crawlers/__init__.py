"""Crawlers for retrieving TDoc and meeting metadata from 3GPP resources."""

from __future__ import annotations

from importlib import import_module
from typing import Any

# No direct imports for any symbols listed in __all__; all are dynamically imported via __getattr__
# TODO: Why is this complicated dynamic import needed? Must be simplified dramatically!

__all__ = [
    "EXCLUDED_DIRS",
    "EXCLUDED_DIRS_NORMALIZED",
    "MEETING_CODE_REGISTRY",
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
    "fetch_meeting_document_list",
    "fetch_meeting_tdocs",
    "fetch_tdoc_metadata",
    "normalize_subgroup_alias",
    "normalize_working_group_alias",
    "parse_excel_document_list",
    "parse_tdoc_portal_page",
    "resolve_via_whatthespec",
]
# TODO: overcomplicated dynamic import mechanism; simplify!
_ATTR_MODULES: dict[str, tuple[str, str]] = {
    "DocumentListError": ("tdoc_crawler.crawlers.meeting_doclist", "DocumentListError"),
    "EXCLUDED_DIRS": ("tdoc_crawler.crawlers.constants", "EXCLUDED_DIRS"),
    "EXCLUDED_DIRS_NORMALIZED": ("tdoc_crawler.crawlers.constants", "EXCLUDED_DIRS_NORMALIZED"),
    "HybridCrawlResult": ("tdoc_crawler.crawlers.hybrid", "HybridCrawlResult"),
    "HybridTDocCrawler": ("tdoc_crawler.crawlers.hybrid", "HybridTDocCrawler"),
    "MEETING_CODE_REGISTRY": ("tdoc_crawler.crawlers.constants", "MEETING_CODE_REGISTRY"),
    "MeetingCrawlResult": ("tdoc_crawler.crawlers.meetings", "MeetingCrawlResult"),
    "MeetingCrawler": ("tdoc_crawler.crawlers.meetings", "MeetingCrawler"),
    "PortalAuthenticationError": ("tdoc_crawler.crawlers.portal", "PortalAuthenticationError"),
    "PortalParsingError": ("tdoc_crawler.crawlers.portal", "PortalParsingError"),
    "PortalSession": ("tdoc_crawler.crawlers.portal", "PortalSession"),
    "TDOC_PATTERN": ("tdoc_crawler.crawlers.constants", "TDOC_PATTERN"),
    "TDOC_PATTERN_STR": ("tdoc_crawler.crawlers.constants", "TDOC_PATTERN_STR"),
    "TDOC_SUBDIRS": ("tdoc_crawler.crawlers.constants", "TDOC_SUBDIRS"),
    "TDOC_SUBDIRS_NORMALIZED": ("tdoc_crawler.crawlers.constants", "TDOC_SUBDIRS_NORMALIZED"),
    "TDocCrawlResult": ("tdoc_crawler.crawlers.tdocs", "TDocCrawlResult"),
    "TDocCrawler": ("tdoc_crawler.crawlers.tdocs", "TDocCrawler"),
    "WhatTheSpecResolutionError": ("tdoc_crawler.crawlers.whatthespec", "WhatTheSpecResolutionError"),
    "convert_excel_row_to_tdoc_metadata": ("tdoc_crawler.crawlers.meeting_doclist", "convert_excel_row_to_tdoc_metadata"),
    "fetch_meeting_document_list": ("tdoc_crawler.crawlers.meeting_doclist", "fetch_meeting_document_list"),
    "fetch_meeting_tdocs": ("tdoc_crawler.crawlers.parallel", "fetch_meeting_tdocs"),
    "fetch_tdoc_metadata": ("tdoc_crawler.crawlers.portal", "fetch_tdoc_metadata"),
    "normalize_subgroup_alias": ("tdoc_crawler.crawlers.meetings", "normalize_subgroup_alias"),
    "normalize_working_group_alias": ("tdoc_crawler.crawlers.meetings", "normalize_working_group_alias"),
    "parse_excel_document_list": ("tdoc_crawler.crawlers.meeting_doclist", "parse_excel_document_list"),
    "parse_tdoc_portal_page": ("tdoc_crawler.crawlers.portal", "parse_tdoc_portal_page"),
    "resolve_via_whatthespec": ("tdoc_crawler.crawlers.whatthespec", "resolve_via_whatthespec"),
}


# TODO: overcomplicated dynamic import mechanism; simplify!
def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _ATTR_MODULES[name]
    except KeyError as exc:
        raise AttributeError(f"module 'tdoc_crawler.crawlers' has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


# TODO: overcomplicated dynamic import mechanism; simplify!
def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
