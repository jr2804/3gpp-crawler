"""Unified configuration service providing access to all config types."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config import CacheManager, resolve_cache_manager
from tdoc_crawler.models.base import HttpCacheConfig
from tdoc_crawler.models.crawl_limits import CrawlLimits

try:
    from tdoc_crawler.ai.config import AiConfig as _AiConfig
    from tdoc_crawler.ai.container import AiServiceContainer
except ImportError:
    _AiConfig = None  # type: ignore[assignment,misc]


class ConfigService:
    """Unified access point for all application configuration.

    Provides lazy access to cache settings, HTTP cache settings,
    AI settings, and crawl limits. Integrates with the existing
    CacheManager registry and ServiceContainer pattern.

    Example:
        config = ConfigService()
        http_config = config.http_cache
        crawl_limits = config.crawl_limits
    """

    def __init__(
        self,
        cache_manager_name: str | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize ConfigService.

        Args:
            cache_manager_name: Name of an already-registered CacheManager to use.
                If None, uses the 'default' manager when available, or creates one
                from environment variables.
            cache_dir: Explicit cache root path. Only used if no CacheManager is
                registered under cache_manager_name. Takes precedence over env vars.
        """
        self._cache_manager_name = cache_manager_name
        self._cache_dir = cache_dir
        self._http_cache: HttpCacheConfig | None = None
        self._crawl_limits: CrawlLimits | None = None

    @property
    def cache_manager(self) -> CacheManager:
        """Return the resolved CacheManager instance.

        Returns:
            The registered CacheManager for this service's name, or the
            default manager if no name was provided.

        Raises:
            ValueError: If no matching CacheManager is registered and no
                cache_dir was provided to create one.
        """
        try:
            return resolve_cache_manager(self._cache_manager_name)
        except ValueError:
            # No registered manager - create one from cache_dir or env
            manager = CacheManager(
                root_path=self._cache_dir,
                name=self._cache_manager_name or "default",
                ensure_paths=True,
            )
            manager.register(force=True)
            return manager

    @property
    def http_cache(self) -> HttpCacheConfig:
        """Return HTTP cache configuration resolved from env vars and defaults.

        Returns:
            HttpCacheConfig instance with resolved TTL and refresh settings.
        """
        if self._http_cache is None:
            self._http_cache = HttpCacheConfig.resolve_http_cache_config(cache_file=self.cache_manager.http_cache_file)
        return self._http_cache

    @property
    def crawl_limits(self) -> CrawlLimits:
        """Return crawl limits with all limits unset (use CLI overrides as needed).

        Returns:
            CrawlLimits instance with no restrictions applied.
        """
        if self._crawl_limits is None:
            self._crawl_limits = CrawlLimits()
        return self._crawl_limits

    def get_ai_config(self, **overrides: str | int | Path | None) -> object:
        """Return AI configuration loaded from container.

        Args:
            **overrides: Not supported - all config comes from container.

        Returns:
            AiConfig instance configured from container.

        Raises:
            ImportError: If the AI extras are not installed.
        """
        if _AiConfig is None:
            msg = "AI extras are not installed. Run: uv add tdoc-crawler[ai]"
            raise ImportError(msg)
        # Use container for config instead of direct from_env() call
        return AiServiceContainer.get_instance().get_config()

    @classmethod
    def from_env(cls, cache_manager_name: str | None = None) -> ConfigService:
        """Create ConfigService loading settings from environment variables.

        Args:
            cache_manager_name: Optional name for the CacheManager to use.

        Returns:
            ConfigService instance configured from the environment.
        """
        return cls(cache_manager_name=cache_manager_name)


__all__ = ["ConfigService"]
