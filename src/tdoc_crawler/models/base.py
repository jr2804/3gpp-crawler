"""Base configuration classes and shared utilities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel


def utc_now() -> datetime:
    """Return the current UTC timestamp as an aware datetime."""
    return datetime.now(UTC)


def _normalize_tdoc_ids(ids: Iterable[str]) -> list[str]:
    """Uppercase and strip whitespace from TDoc identifiers."""
    return [str(value).strip().upper() for value in ids]


class OutputFormat(StrEnum):
    """Supported output formats for CLI responses."""

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


class SortOrder(StrEnum):
    """Sort orders accepted by query operations."""

    ASC = "asc"
    DESC = "desc"


class BaseConfigModel(BaseModel):
    """Shared configuration base enabling attribute parsing and whitespace handling."""

    model_config = {"str_strip_whitespace": True, "use_enum_values": False}


@dataclass
class PortalCredentials:
    """Credentials required for ETSI Online Account (EOL) protected resources."""

    username: str
    password: str


@dataclass
class HttpCacheConfig:
    """HTTP cache configuration for hishel caching."""

    ttl: int = 7200
    refresh_ttl_on_access: bool = True


__all__ = [
    "DEFAULT_CACHE_DIR",
    "BaseConfigModel",
    "HttpCacheConfig",
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
    "_normalize_tdoc_ids",
    "utc_now",
]
