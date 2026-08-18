"""Base configuration classes and shared utilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto


class TagKind(StrEnum):
    """Kind of item a tag is attached to."""

    TDOC = "tdoc"
    SPEC = "spec"
    OTHER = "other"


class OutputFormat(StrEnum):
    """Supported output formats for CLI responses."""

    TABLE = auto()
    JSON = auto()
    ISON = auto()
    TOON = auto()
    YAML = auto()


class SortOrder(StrEnum):
    """Sort orders accepted by query operations."""

    ASC = auto()
    DESC = auto()


@dataclass
class PortalCredentials:
    """Credentials required for ETSI Online Account (EOL) protected resources."""

    username: str
    password: str


__all__ = [
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
]
