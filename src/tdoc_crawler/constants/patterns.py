"""Regex patterns for parsing 3GPP data."""

from __future__ import annotations

import re
from typing import Final

TDOC_PATTERN_STR: Final[str] = r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)"
TDOC_PATTERN: Final[re.Pattern[str]] = re.compile(TDOC_PATTERN_STR, re.IGNORECASE)

DATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"(\d{4}[\-\u2010-\u2015]\d{2}[\-\u2010-\u2015]\d{2})")

TDOC_SUBDIRS: Final[tuple[str, ...]] = ("Docs", "Documents", "Tdocs", "TDocs", "DOCS")
TDOC_SUBDIRS_NORMALIZED: Final[frozenset[str]] = frozenset(entry.upper() for entry in TDOC_SUBDIRS)

EXCLUDED_DIRS: Final[tuple[str, ...]] = ("Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report")
EXCLUDED_DIRS_NORMALIZED: Final[frozenset[str]] = frozenset(entry.upper() for entry in EXCLUDED_DIRS)

__all__ = [
    "DATE_PATTERN",
    "EXCLUDED_DIRS",
    "EXCLUDED_DIRS_NORMALIZED",
    "TDOC_PATTERN",
    "TDOC_PATTERN_STR",
    "TDOC_SUBDIRS",
    "TDOC_SUBDIRS_NORMALIZED",
]
