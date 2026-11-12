"""Base configuration classes and shared utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, auto

from tdoc_crawler.utils.version_types import AgendaItem

type TDocFieldValue = str | int | bool | datetime | AgendaItem | None
"""Value of a TDoc metadata field (as stored, updated or refreshed)."""


class DocumentType(StrEnum):
    """Document types considered the "main" file of a TDoc archive.

    Declaration order is the main-file selection preference order
    (best first). Subjective ordering — make configurable if it ever bites.
    """

    DOCX = ".docx"
    PPTX = ".pptx"
    PPT = ".ppt"
    PDF = ".pdf"
    XLSX = ".xlsx"
    DOC = ".doc"
    XLS = ".xls"


class OutputFormat(StrEnum):
    """Supported output formats for CLI responses."""

    TABLE = auto()
    JSON = auto()
    ISON = auto()
    TOON = auto()
    YAML = auto()


class SortKey(StrEnum):
    """Sort keys for TDoc query ordering."""

    MEETING_DATE = "meeting_date"  # default: meeting start_date, then tdoc_id
    RESERVATION_DATE = "reservation_date"
    UPLOADED_AT = "uploaded_at"
    TDOC_ID = "tdoc_id"


class SortOrder(StrEnum):
    """Sort orders accepted by query operations."""

    ASC = auto()
    DESC = auto()


class TagKind(StrEnum):
    """Kind of item a tag is attached to."""

    TDOC = "tdoc"
    SPEC = "spec"
    OTHER = "other"


@dataclass
class PortalCredentials:
    """Credentials required for ETSI Online Account (EOL) protected resources."""

    username: str
    password: str


__all__ = [
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
    "TDocFieldValue",
]
