"""Base configuration classes and shared utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from tdoc_crawler.config import resolve_cache_manager


class OutputFormat(StrEnum):
    """Supported output formats for CLI responses."""

    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


class SortOrder(StrEnum):
    """Sort orders accepted by query operations."""

    ASC = "asc"
    DESC = "desc"


_DEFAULT_TTL: int = 7200
_DEFAULT_TTL_ON_ACCESS: bool = True
_DEFAULT_MAX_RETRIES: int = 3


@dataclass
class HttpCacheConfig:
    """HTTP cache configuration for hishel caching."""

    ttl: int = _DEFAULT_TTL
    refresh_ttl_on_access: bool = _DEFAULT_TTL_ON_ACCESS
    max_retries: int = _DEFAULT_MAX_RETRIES
    cache_file: Path | None = None

    @classmethod
    def resolve_http_cache_config(
        cls,
        cache_ttl: int | None = None,
        cache_refresh_on_access: bool | None = None,
        max_retries: int | None = None,
        cache_file: Path | None = None,
    ) -> HttpCacheConfig:
        """Resolve HTTP cache configuration from CLI parameters and environment variables.

        Args:
            cache_ttl: TTL for cache entries (CLI parameter)
            cache_refresh_on_access: Whether to refresh TTL on access (CLI parameter)
            max_retries: Maximum number of retry attempts for failed requests (CLI parameter)
            cache_file: Optional explicit cache file path (CLI parameter). If not provided, will be determined by CacheManager.

        Returns:
            HttpCacheConfig instance with resolved values
        """
        # Check CLI parameters first, then environment variables, then defaults
        if cache_ttl is not None:
            ttl = cache_ttl
        else:
            env_ttl = os.getenv("HTTP_CACHE_TTL")
            ttl = int(env_ttl) if env_ttl else _DEFAULT_TTL

        # Handle refresh on access - check CLI param, then env var, then default
        if cache_refresh_on_access is not None:
            refresh_on_access = cache_refresh_on_access
        elif env_refresh := os.getenv("HTTP_CACHE_REFRESH_ON_ACCESS"):
            env_refresh = env_refresh.lower()
            refresh_on_access = env_refresh in ("true", "1", "yes", "on", "t", "y")
        else:
            refresh_on_access = _DEFAULT_TTL_ON_ACCESS

        max_retries = max_retries or _DEFAULT_MAX_RETRIES
        return HttpCacheConfig(ttl=ttl, refresh_ttl_on_access=refresh_on_access, max_retries=max_retries, cache_file=cache_file)


class BaseConfigModel(BaseModel):
    """Shared configuration base enabling attribute parsing and whitespace handling."""

    model_config = {"str_strip_whitespace": True, "use_enum_values": False}

    cache_manager_name: str | None = Field(default=None, description="Cache configuration manager name")
    http_cache: HttpCacheConfig = Field(default_factory=HttpCacheConfig.resolve_http_cache_config, description="HTTP cache configuration")

    @property
    def cache_dir(self) -> Path:
        """Return the cache directory being used."""
        return resolve_cache_manager(self.cache_manager_name).root


@dataclass
class PortalCredentials:
    """Credentials required for ETSI Online Account (EOL) protected resources."""

    username: str
    password: str


__all__ = [
    "BaseConfigModel",
    "HttpCacheConfig",
    "OutputFormat",
    "PortalCredentials",
    "SortOrder",
]
