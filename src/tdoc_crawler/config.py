"""Configuration management for file paths and caching behavior."""

from __future__ import annotations

import os
from pathlib import Path

# Fallback path if no argument or env var is provided
DEFAULT_CACHE_DIR = Path.home() / ".tdoc-crawler"
DEFAULT_DATABASE_FILENAME = "tdoc_crawler.db"
DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
DEFAULT_CHECKOUT_DIRNAME = "checkout"


class CacheManager:
    """Manages cache directory layout and path resolution.

    Acts as the single source of truth for where files are stored.
    """

    def __init__(self, root_path: Path | None = None) -> None:
        """Initialize cache manager.

        Args:
            root_path: Explicit root path. If None, tries TDC_CACHE_DIR env var,
                       then falls back to DEFAULT_CACHE_DIR.
        """
        if root_path:
            self.root = root_path
        else:
            env_path = os.getenv("TDC_CACHE_DIR")
            self.root = Path(env_path) if env_path else DEFAULT_CACHE_DIR

    @property
    def http_cache_path(self) -> Path:
        """Path to the HTTP client cache database."""
        return self.root / DEFAULT_HTTP_CACHE_FILENAME

    @property
    def db_path(self) -> Path:
        """Path to the metadata SQLite database."""
        return self.root / DEFAULT_DATABASE_FILENAME

    @property
    def checkout_dir(self) -> Path:
        """Path to the default checkout directory."""
        return self.root / DEFAULT_CHECKOUT_DIRNAME

    def ensure_paths(self) -> None:
        """Ensure the root cache directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)
