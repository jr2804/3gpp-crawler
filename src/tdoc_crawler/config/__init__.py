"""Configuration management for 3GPP Crawler."""

from __future__ import annotations

from tdoc_crawler.config.cache_manager import (
    DEFAULT_AI_CACHE_DIRNAME,
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
    TDocCrawlerConfig,
    ThreeGPPConfig,
)
from tdoc_crawler.config.sources import (
    ConfigLoadError,
    discover_config_files,
    load_config_file,
    merge_configs,
)

__all__ = [
    # CacheManager
    "CacheManager",
    "CacheManagerNotRegisteredError",
    "resolve_cache_manager",
    "DEFAULT_DATABASE_FILENAME",
    "DEFAULT_HTTP_CACHE_FILENAME",
    "DEFAULT_CHECKOUT_DIRNAME",
    "DEFAULT_AI_CACHE_DIRNAME",
    # Settings
    "CrawlConfig",
    "CredentialsConfig",
    "HttpConfig",
    "PathConfig",
    "TDocCrawlerConfig",
    "ThreeGPPConfig",
    # Config sources
    "ConfigEnvVar",
    "ConfigLoadError",
    "TOML_PATH_TO_ENV_VAR",
    "discover_config_files",
    "load_config_file",
    "merge_configs",
]
