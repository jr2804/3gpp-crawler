"""Shared constants and lookup tables for crawler modules."""

from __future__ import annotations

import re
from typing import Final

TDOC_PATTERN_STR: Final[str] = r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)"
TDOC_PATTERN: Final[re.Pattern[str]] = re.compile(TDOC_PATTERN_STR, re.IGNORECASE)

TDOC_SUBDIRS: Final[tuple[str, ...]] = ("Docs", "Documents", "Tdocs", "TDocs", "DOCS")
TDOC_SUBDIRS_NORMALIZED: Final[frozenset[str]] = frozenset(entry.upper() for entry in TDOC_SUBDIRS)

EXCLUDED_DIRS: Final[tuple[str, ...]] = ("Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report")
EXCLUDED_DIRS_NORMALIZED: Final[frozenset[str]] = frozenset(entry.upper() for entry in EXCLUDED_DIRS)

MEETINGS_BASE_URL: Final[str] = "https://www.3gpp.org/dynareport?code=Meetings-{code}.htm"
PORTAL_BASE_URL: Final[str] = "https://portal.3gpp.org"
TDOC_VIEW_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/CreateTdoc.Aspx"
LOGIN_URL: Final[str] = f"{PORTAL_BASE_URL}/login.aspx"

DATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"(\d{4}[\-\u2010-\u2015]\d{2}[\-\u2010-\u2015]\d{2})")

MEETING_CODE_REGISTRY: Final[dict[str, list[tuple[str, str | None]]]] = {
    "RAN": [
        ("RP", "RP"),
        ("R1", "R1"),
        ("R2", "R2"),
        ("R3", "R3"),
        ("R4", "R4"),
        ("R5", "R5"),
        ("R6", "R6"),
    ],
    "SA": [
        ("SP", "SP"),
        ("S1", "S1"),
        ("S2", "S2"),
        ("S3", "S3"),
        ("S4", "S4"),
        ("S5", "S5"),
        ("S6", "S6"),
    ],
    "CT": [
        ("CP", "CP"),
        ("C1", "C1"),
        ("C2", "C2"),
        ("C3", "C3"),
        ("C4", "C4"),
        ("C5", "C5"),
        ("C6", "C6"),
    ],
}

__all__ = [
    "DATE_PATTERN",
    "EXCLUDED_DIRS",
    "EXCLUDED_DIRS_NORMALIZED",
    "LOGIN_URL",
    "MEETINGS_BASE_URL",
    "MEETING_CODE_REGISTRY",
    "PORTAL_BASE_URL",
    "TDOC_PATTERN",
    "TDOC_PATTERN_STR",
    "TDOC_SUBDIRS",
    "TDOC_SUBDIRS_NORMALIZED",
    "TDOC_VIEW_URL",
]
