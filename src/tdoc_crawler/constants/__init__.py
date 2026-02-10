"""Shared constants and registries."""

from __future__ import annotations

from tdoc_crawler.constants.patterns import (
    DATE_PATTERN,
    EXCLUDED_DIRS,
    EXCLUDED_DIRS_NORMALIZED,
    TDOC_PATTERN,
    TDOC_PATTERN_STR,
    TDOC_SUBDIRS,
    TDOC_SUBDIRS_NORMALIZED,
)
from tdoc_crawler.constants.registry import MEETING_CODE_REGISTRY
from tdoc_crawler.constants.urls import (
    LOGIN_URL,
    MEETINGS_BASE_URL,
    PORTAL_BASE_URL,
    SPEC_URL_TEMPLATE,
    TDOC_DOWNLOAD_URL,
    TDOC_VIEW_URL,
)

__all__ = [
    "DATE_PATTERN",
    "EXCLUDED_DIRS",
    "EXCLUDED_DIRS_NORMALIZED",
    "LOGIN_URL",
    "MEETINGS_BASE_URL",
    "MEETING_CODE_REGISTRY",
    "PORTAL_BASE_URL",
    "SPEC_URL_TEMPLATE",
    "TDOC_DOWNLOAD_URL",
    "TDOC_PATTERN",
    "TDOC_PATTERN_STR",
    "TDOC_SUBDIRS",
    "TDOC_SUBDIRS_NORMALIZED",
    "TDOC_VIEW_URL",
]
