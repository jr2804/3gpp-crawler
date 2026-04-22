"""Cache manager for centralized path management.

This module provides the CacheManager class for managing file system paths
in a centralized, configurable manner. All paths should be accessed through
the CacheManager to ensure consistency and testability.

Usage:
    # At application entry point (CLI __main__.py)
    from tdoc_crawler.config import CacheManager

    cache_dir = Path.home() / ".3gpp-crawler"  # Or from config/env var
    manager = CacheManager(cache_dir).register()

    # Anywhere else in the codebase
    from tdoc_crawler.config import resolve_cache_manager

    manager = resolve_cache_manager()
    db_path = manager.db_file
    checkout_path = manager.checkout_dir
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from tdoc_crawler.config.settings import WORKSPACE_REGISTRY_FILENAME

DEFAULT_DATABASE_FILENAME = "3gpp_crawler.db"
DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
DEFAULT_CHECKOUT_DIRNAME = "checkout"
DEFAULT_AI_CACHE_DIRNAME = "lightrag"


class CacheManagerNotRegisteredError(RuntimeError):
    """Raised when trying to resolve CacheManager before registration."""

    pass


class CacheManager:
    """Centralized manager for cache directory paths.

    Provides a single source of truth for all file system paths used by
    the application. The manager must be registered once at application
    startup, then resolved wherever paths are needed.

    Example:
        >>> # At application entry
        >>> manager = CacheManager(cache_dir).register()
        >>>
        >>> # Anywhere else
        >>> manager = resolve_cache_manager()
        >>> db_path = manager.db_file
    """

    _instance: ClassVar[CacheManager | None] = None

    def __init__(self, cache_dir: Path) -> None:
        """Initialize the cache manager.

        Args:
            cache_dir: Root cache directory path
        """
        self._cache_dir = cache_dir.resolve()

    def register(self) -> CacheManager:
        """Register this instance as the global CacheManager.

        Returns:
            Self for chaining

        Raises:
            RuntimeError: If a manager is already registered
        """
        if CacheManager._instance is not None:
            raise RuntimeError("CacheManager already registered. Call only once at startup.")
        CacheManager._instance = self
        return self

    @property
    def root(self) -> Path:
        """Root cache directory."""
        return self._cache_dir

    @property
    def db_file(self) -> Path:
        """Path to SQLite database file."""
        return self._cache_dir / DEFAULT_DATABASE_FILENAME

    @property
    def http_cache_file(self) -> Path:
        """Path to HTTP cache database file."""
        return self._cache_dir / DEFAULT_HTTP_CACHE_FILENAME

    @property
    def checkout_dir(self) -> Path:
        """Path to checkout directory for documents."""
        return self._cache_dir / DEFAULT_CHECKOUT_DIRNAME

    @property
    def ai_cache_dir(self) -> Path:
        """Path to AI cache directory for embeddings and graphs."""
        return self._cache_dir / DEFAULT_AI_CACHE_DIRNAME

    @property
    def ai_workspace_file(self) -> Path:
        """Path to workspace registry file."""
        return self.ai_cache_dir / WORKSPACE_REGISTRY_FILENAME

    def ai_embed_dir(self, embedding_model: str) -> Path:
        """Path to embeddings directory for a specific model.

        Args:
            embedding_model: Name of the embedding model

        Returns:
            Path to model-specific embeddings directory
        """
        return (self.ai_cache_dir / embedding_model).resolve()

    @classmethod
    def is_registered(cls) -> bool:
        """Check if a CacheManager instance is registered.

        Returns:
            True if registered, False otherwise
        """
        return cls._instance is not None


def resolve_cache_manager() -> CacheManager:
    """Resolve the registered CacheManager instance.

    Returns:
        The registered CacheManager instance

    Raises:
        CacheManagerNotRegisteredError: If no manager is registered
    """
    if CacheManager._instance is None:
        raise CacheManagerNotRegisteredError("CacheManager not registered. Call CacheManager(cache_dir).register() at application startup.")
    return CacheManager._instance
