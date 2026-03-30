"""Configuration settings for TDocCrawler using pydantic-settings.

This module provides the TDocCrawlerConfig class with nested models for:
- PathConfig: File system paths (cache, checkout, AI store)
- HttpConfig: HTTP caching and request behavior
- CredentialsConfig: Portal authentication credentials
- CrawlConfig: Crawling behavior and filters

All paths default to values from CacheManager but can be overridden via
environment variables with the TDC_ prefix.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default values matching those in __init__.py
_DEFAULT_CACHE_DIR = Path.home() / ".3gpp-crawler"
_DEFAULT_DATABASE_FILENAME = "3gpp_crawler.db"
_DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
_DEFAULT_CHECKOUT_DIRNAME = "checkout"
_DEFAULT_AI_CACHE_DIRNAME = "lightrag"


class PathConfig(BaseSettings):
    """File system path configuration.

    Provides paths for cache directory, database, checkout, and AI storage.
    All paths support ~ expansion and are resolved to absolute paths.
    """

    model_config = SettingsConfigDict(env_prefix="TDC_", env_nested_delimiter="_", extra="ignore")

    cache_dir: Path = Field(
        default=_DEFAULT_CACHE_DIR,
        validation_alias=AliasChoices("TDC_CACHE_DIR", "cache_dir"),
        description="Root cache directory for storing downloaded files and metadata",
    )
    db_filename: str = Field(
        default=_DEFAULT_DATABASE_FILENAME,
        description="SQLite database filename for storing crawl metadata",
    )
    checkout_dirname: str = Field(
        default=_DEFAULT_CHECKOUT_DIRNAME,
        description="Subdirectory name for checked-out documents",
    )
    ai_cache_dirname: str = Field(
        default=_DEFAULT_AI_CACHE_DIRNAME,
        description="Subdirectory name for AI-related cache (embeddings, graphs)",
    )

    @property
    def db_file(self) -> Path:
        """Path to the SQLite database file."""
        return self.cache_dir / _DEFAULT_DATABASE_FILENAME

    @property
    def http_cache_file(self) -> Path:
        """Path to the HTTP cache database file."""
        return self.cache_dir / _DEFAULT_HTTP_CACHE_FILENAME

    @property
    def checkout_dir(self) -> Path:
        """Path to the checkout directory for documents."""
        return self.cache_dir / _DEFAULT_CHECKOUT_DIRNAME

    @property
    def ai_cache_dir(self) -> Path:
        """Path to the AI cache directory for embeddings and graphs."""
        return self.cache_dir / _DEFAULT_AI_CACHE_DIRNAME

    def ai_embed_dir(self, embedding_model: str) -> Path:
        """Path to store AI-related files for a specific embedding model.

        Args:
            embedding_model: The embedding model identifier.

        Returns:
            Path to the model-specific AI directory.
        """
        return (self.ai_cache_dir / embedding_model).resolve()

    @field_validator("cache_dir", mode="before")
    @classmethod
    def _resolve_cache_dir(cls, value: str | Path | None) -> Path:
        """Resolve and validate the cache directory path."""
        if value is None:
            return _DEFAULT_CACHE_DIR
        if isinstance(value, str):
            value = Path(value)
        return value.expanduser().resolve()


class HttpConfig(BaseSettings):
    """HTTP client and caching configuration.

    Controls HTTP request behavior including timeouts, retries,
    and caching behavior for web requests.
    """

    model_config = SettingsConfigDict(env_prefix="", env_nested_delimiter="_", extra="ignore")

    cache_ttl: int = Field(
        default=7200,
        ge=0,
        validation_alias=AliasChoices("HTTP_CACHE_TTL", "cache_ttl"),
        description="Time-to-live for HTTP cache entries in seconds",
    )
    cache_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("HTTP_CACHE_ENABLED", "cache_enabled"),
        description="Enable HTTP response caching",
    )
    cache_refresh_on_access: bool = Field(
        default=True,
        validation_alias=AliasChoices("HTTP_CACHE_REFRESH_ON_ACCESS", "cache_refresh_on_access"),
        description="Refresh cache TTL on each access",
    )
    verify_ssl: bool = Field(
        default=True,
        validation_alias=AliasChoices("TDC_VERIFY_SSL", "verify_ssl"),
        description="Verify SSL certificates for HTTPS requests",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        validation_alias=AliasChoices("TDC_MAX_RETRIES", "max_retries"),
        description="Maximum number of retry attempts for failed requests",
    )
    timeout: int = Field(
        default=30,
        ge=1,
        validation_alias=AliasChoices("TDC_TIMEOUT", "timeout"),
        description="HTTP request timeout in seconds",
    )

    @field_validator("cache_ttl", "max_retries", "timeout", mode="before")
    @classmethod
    def _parse_int(cls, value: str | int | None) -> int:
        """Parse integer values from environment strings."""
        if value is None:
            return 0 if cls.__name__ in ("HttpConfig",) else 0
        if isinstance(value, str):
            value = value.strip()
            return int(value) if value else 0
        return int(value)

    @field_validator("cache_enabled", "cache_refresh_on_access", "verify_ssl", mode="before")
    @classmethod
    def _parse_bool(cls, value: bool | str | None) -> bool:
        """Parse boolean values from environment strings."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.strip().lower()
            return value in ("true", "1", "yes", "on", "t", "y")
        return bool(value)


class CredentialsConfig(BaseSettings):
    """Portal authentication credentials.

    Stores credentials for accessing protected resources like the 3GPP portal.
    """

    model_config = SettingsConfigDict(env_prefix="TDC_EOL_", env_nested_delimiter="_", extra="ignore")

    username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_EOL_USERNAME", "username"),
        description="Username for ETSI Online (EOL) portal authentication",
    )
    password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_EOL_PASSWORD", "password"),
        description="Password for ETSI Online (EOL) portal authentication",
    )
    prompt: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_EOL_PROMPT", "prompt"),
        description="Custom prompt message for interactive credential entry",
    )

    @property
    def has_credentials(self) -> bool:
        """Check if both username and password are set."""
        return bool(self.username and self.password)


class CrawlConfig(BaseSettings):
    """Crawling behavior and filter configuration.

    Controls which documents are crawled based on working groups,
    date ranges, and other filters.
    """

    model_config = SettingsConfigDict(env_prefix="TDC_CRAWL_", env_nested_delimiter="_", extra="ignore")

    working_group: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_WORKING_GROUP", "working_group"),
        description="Filter by working group (e.g., S4, RAN1, CT3)",
    )
    sub_group: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_SUB_GROUP", "sub_group"),
        description="Filter by sub-working group",
    )
    date_start: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_START_DATE", "date_start"),
        description="Start date filter (YYYY-MM-DD, YYYY-MM, or YYYY format)",
    )
    date_end: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_END_DATE", "date_end"),
        description="End date filter (YYYY-MM-DD, YYYY-MM, or YYYY format)",
    )
    source_like: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_SOURCE_LIKE", "source_like"),
        description="SQL LIKE pattern to match document source",
    )
    agenda_like: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_AGENDA_LIKE", "agenda_like"),
        description="SQL LIKE pattern to match agenda item",
    )
    title_like: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TDC_TITLE_LIKE", "title_like"),
        description="SQL LIKE pattern to match document title",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        validation_alias=AliasChoices("TDC_LIMIT_TDOCS", "limit"),
        description="Maximum number of documents to crawl",
    )
    workers: int = Field(
        default=4,
        ge=1,
        le=32,
        validation_alias=AliasChoices("TDC_WORKERS", "workers"),
        description="Number of concurrent workers for crawling",
    )


class TDocCrawlerConfig(BaseSettings):
    """Main configuration class for TDocCrawler.

    Aggregates all configuration sub-models:
    - path: File system paths
    - http: HTTP client and caching behavior
    - credentials: Portal authentication
    - crawl: Crawling filters and limits

    Configuration can be overridden via environment variables with the
    appropriate prefixes (TDC_, TDC_EOL_, TDC_CRAWL_).
    """

    model_config = SettingsConfigDict(
        env_prefix="TDC_",
        env_nested_delimiter="_",
        extra="ignore",
    )

    path: PathConfig = Field(default_factory=PathConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    credentials: CredentialsConfig = Field(default_factory=CredentialsConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)

    def ensure_paths(self) -> None:
        """Ensure all configured paths exist on the filesystem.

        Creates parent directories as needed.
        """
        self.path.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path.checkout_dir.mkdir(parents=True, exist_ok=True)
        self.path.ai_cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_settings(
        cls,
        config_file: Path | str | None = None,
        cwd: Path | str | None = None,
    ) -> TDocCrawlerConfig:
        """Create a TDocCrawlerConfig instance with config file and environment values.

        Config precedence (highest to lowest):
        1. CLI explicit config_file parameter
        2. Discovered config files (later override earlier)
        3. Environment variables (TDC_*)
        4. Hard-coded defaults

        Args:
            config_file: Explicit path to a config file. If provided, only this
                file is loaded (no discovery).
            cwd: Working directory for project-level config discovery.
                 Defaults to current working directory.

        Returns:
            A validated TDocCrawlerConfig instance.
        """
        # Import via import_module to avoid PLC0415 and circular import
        sources = import_module("tdoc_crawler.config.sources")
        discover_config_files = sources.discover_config_files
        load_config_file = sources.load_config_file
        merge_configs = sources.merge_configs

        cwd_path = Path(cwd) if cwd is not None else Path.cwd()

        if config_file:
            config_path = Path(config_file)
            merged = load_config_file(config_path)
        else:
            discovered = discover_config_files(cwd=cwd_path)
            configs = [load_config_file(p) for p in discovered]
            merged = merge_configs(configs)

        return cls(**merged)


__all__ = [
    "CrawlConfig",
    "CredentialsConfig",
    "HttpConfig",
    "PathConfig",
    "TDocCrawlerConfig",
]
