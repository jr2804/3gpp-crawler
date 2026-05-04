"""Configuration management for 3GPP Crawler."""

from __future__ import annotations

from tdoc_crawler.config.cache_manager import (
    DEFAULT_CHECKOUT_DIRNAME,
    DEFAULT_DATABASE_FILENAME,
    DEFAULT_HTTP_CACHE_FILENAME,
    CacheManager,
    CacheManagerNotRegisteredError,
    resolve_cache_manager,
)
from tdoc_crawler.config.env_vars import TOML_PATH_TO_ENV_VAR, ConfigEnvVar
from tdoc_crawler.config.settings import (
    CrawlConfig,
    CredentialsConfig,
    HttpConfig,
    PathConfig,
    ThreeGPPConfig,
)
from tdoc_crawler.config.sources import (
    ConfigLoadError,
    discover_config_files,
    load_config_file,
    merge_configs,
)

__all__ = [
    "DEFAULT_CHECKOUT_DIRNAME",
    "DEFAULT_DATABASE_FILENAME",
    "DEFAULT_HTTP_CACHE_FILENAME",
    "TOML_PATH_TO_ENV_VAR",
    # CacheManager
    "CacheManager",
    "CacheManagerNotRegisteredError",
    # Config sources
    "ConfigEnvVar",
    "ConfigLoadError",
    # Settings
    "CrawlConfig",
    "CredentialsConfig",
    "HttpConfig",
    "PathConfig",
    "ThreeGPPConfig",
    "discover_config_files",
    "load_config_file",
    "merge_configs",
    "resolve_cache_manager",
]
