"""Base configuration classes and shared utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel


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

    @classmethod
    def resolve_http_cache_config(cls, cache_ttl: int | None = None, cache_refresh_on_access: bool | None = None) -> HttpCacheConfig:
        """Resolve HTTP cache configuration from CLI parameters and environment variables.

        Args:
            cache_ttl: TTL for cache entries (CLI parameter)
            cache_refresh_on_access: Whether to refresh TTL on access (CLI parameter)

        Returns:
            HttpCacheConfig instance with resolved values
        """
        # Check CLI parameters first, then environment variables, then defaults
        if cache_ttl is not None:
            ttl = cache_ttl
        else:
            env_ttl = os.getenv("HTTP_CACHE_TTL")
            ttl = int(env_ttl) if env_ttl else 7200

        # Handle refresh on access - check CLI param, then env var, then default
        if cache_refresh_on_access is not None:
            refresh_on_access = cache_refresh_on_access
        else:
            env_refresh = os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS", "").lower()
            refresh_on_access = env_refresh in ("true", "1", "yes", "on", "t", "y") if env_refresh else True

        return HttpCacheConfig(ttl=ttl, refresh_ttl_on_access=refresh_on_access)


__all__ = [
    "BaseConfigModel",
    "HttpCacheConfig",
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
]
