"""Configuration management for file paths and caching behavior."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Self

# Fallback path if no argument or env var is provided
DEFAULT_CACHE_DIR = Path.home() / ".tdoc-crawler"
DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"
DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
DEFAULT_CHECKOUT_DIRNAME = "checkout"

DEFAULT_MANAGER = "default"

_cache_managers: dict[str, CacheManager] = {}


def register_cache_manager(manager: CacheManager, force: bool = False) -> None:
    """Register a cache manager instance under a given name.

    Args:
        manager: CacheManager instance to register
        force: If True, overwrite existing manager with same name
    """
    name = manager.name
    if name in _cache_managers and not force:
        raise ValueError(f"Cache manager with name '{name}' is already registered.")
    _cache_managers[name] = manager


def reset_cache_managers() -> None:
    """Clear all registered cache managers.

    Primarily useful for testing to ensure clean state between tests.
    """
    _cache_managers.clear()


def resolve_cache_manager(name: str | None = None) -> CacheManager:
    """Resolve a cache manager by name, or return the default if name is None."""
    name = name or DEFAULT_MANAGER
    manager = _cache_managers.get(name)
    if manager is None:
        raise ValueError(f"No cache manager registered under name '{name}'.")
    return manager


class CacheManager:
    """Manages cache directory layout and path resolution.

    Acts as the single source of truth for where files are stored.
    """

    def __init__(self, root_path: Path | None = None, name: str = DEFAULT_MANAGER, ensure_paths: bool = True) -> None:
        """Initialize cache manager.

        Args:
            root_path: Explicit root path. If None, tries TDC_CACHE_DIR env var,
                       then falls back to DEFAULT_CACHE_DIR.
            name: Optional name to register this manager under. If provided, the manager is registered upon initialization.
            ensure_paths: If True, will create the root directory if it doesn't exist.
        """
        self.name = name

        if root_path:
            self.root = root_path
        else:
            env_path = os.getenv("TDC_CACHE_DIR")
            self.root = Path(env_path) if env_path else DEFAULT_CACHE_DIR

        if ensure_paths:
            self.ensure_paths()

    def register(self, force: bool = True) -> Self:
        """Register this instance as a cache manager under the given name.

        Args:
            force: If True (default), overwrite existing manager with same name
        """
        register_cache_manager(self, force=force)
        return self

    @property
    def http_cache_file(self) -> Path:
        """Path to the HTTP client cache database file."""
        return self.root / DEFAULT_HTTP_CACHE_FILENAME

    @property
    def db_file(self) -> Path:
        """Path to the metadata SQLite database."""
        return self.root / DEFAULT_DATABASE_FILENAME

    @property
    def checkout_dir(self) -> Path:
        """Path to the default checkout directory."""
        return self.root / DEFAULT_CHECKOUT_DIRNAME

    def ensure_paths(self) -> None:
        """Ensure the root cache directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)
