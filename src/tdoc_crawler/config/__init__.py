"""Configuration management for 3GPP Crawler."""

from __future__ import annotations

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

DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"

__all__ = [
    "DEFAULT_HTTP_CACHE_FILENAME",
    "TOML_PATH_TO_ENV_VAR",
    "ConfigEnvVar",
    "ConfigLoadError",
    "CrawlConfig",
    "CredentialsConfig",
    "HttpConfig",
    "PathConfig",
    "TDocCrawlerConfig",
    "ThreeGPPConfig",
    "discover_config_files",
    "load_config_file",
    "merge_configs",
]
