"""Configuration management for file paths and caching behavior."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Self

# Import settings and sources modules
from tdoc_crawler.config.env_vars import (
    DEPRECATED_ENV_VARS,
    ENV_VAR_MAPPINGS,
    ConfigEnvVar,
    log_deprecation_warning,
)
from tdoc_crawler.config.settings import (
    CrawlConfig,
    CredentialsConfig,
    HttpConfig,
    PathConfig,
    TDocCrawlerConfig,
)
from tdoc_crawler.config.sources import (
    ConfigLoadError,
    discover_config_files,
    load_config_file,
    merge_configs,
)

# Fallback path if no argument or env var is provided
DEFAULT_CACHE_DIR = Path.home() / ".3gpp-crawler"
DEFAULT_DATABASE_FILENAME = "3gpp_crawler.db"
DEFAULT_HTTP_CACHE_FILENAME = "http-cache.sqlite3"
DEFAULT_CHECKOUT_DIRNAME = "checkout"
DEFAULT_MANAGER = "default"

DEFAULT_AI_CACHE_DIRNAME = "lightrag"  # subdirectory under root cache dir for AI-related files

WORKSPACE_REGISTRY_FILENAME = "workspaces.json"

__all__ = [
    "DEFAULT_AI_CACHE_DIRNAME",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_CHECKOUT_DIRNAME",
    "DEFAULT_DATABASE_FILENAME",
    "DEFAULT_HTTP_CACHE_FILENAME",
    "DEFAULT_MANAGER",
    "DEPRECATED_ENV_VARS",
    "ENV_VAR_MAPPINGS",
    "CacheManager",
    "ConfigEnvVar",
    "ConfigLoadError",
    "CrawlConfig",
    "CredentialsConfig",
    "HttpConfig",
    "PathConfig",
    "TDocCrawlerConfig",
    "discover_config_files",
    "load_config_file",
    "log_deprecation_warning",
    "merge_configs",
    "register_cache_manager",
    "reset_cache_managers",
    "resolve_cache_manager",
]

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

    def __init__(
        self,
        root_path: Path | None = None,
        ai_cache_dir: Path | None = None,
        name: str = DEFAULT_MANAGER,
        ensure_paths: bool = True,
        config: TDocCrawlerConfig | None = None,
    ) -> None:
        """Initialize cache manager.

        Args:
            root_path: Explicit root path. If None, tries TDC_CACHE_DIR env var,
                       then falls back to DEFAULT_CACHE_DIR. Ignored if config is provided.
            ai_cache_dir: Explicit AI cache directory path. If None, defaults to root_path/lightrag
                         or TDC_AI_STORE_PATH env var if set. Ignored if config is provided.
            name: Optional name to register this manager under. If provided, the manager is registered upon initialization.
            ensure_paths: If True, will create the root directory if it doesn't exist.
            config: Optional TDocCrawlerConfig to use for path resolution. If provided,
                    config.path.cache_dir and config.path.ai_cache_dir are used.
        """
        self.name = name

        if config is not None:
            # Use config for path resolution (preferred)
            self.root = config.path.cache_dir
            self.ai_cache_dir = config.path.ai_cache_dir
        elif root_path:
            self.root = root_path
        else:
            # Fallback to env var (will be removed in future version)
            env_cache_dir = os.getenv("TDC_CACHE_DIR")
            self.root = Path(env_cache_dir) if env_cache_dir else DEFAULT_CACHE_DIR

        if config is None and not ai_cache_dir:
            env_ai_cache_dir = os.getenv("TDC_AI_STORE_PATH")
            if env_ai_cache_dir:
                self.ai_cache_dir = Path(env_ai_cache_dir).resolve()
            else:
                self.ai_cache_dir = (self.root / DEFAULT_AI_CACHE_DIRNAME).resolve()
        elif ai_cache_dir:
            self.ai_cache_dir = ai_cache_dir.resolve()

        if ensure_paths:
            self.ensure_paths()
            self.ensure_ai_paths()

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

    def ai_embed_dir(self, embedding_model: str) -> Path:
        """Path to store AI-related files for a specific embedding model."""
        return (self.ai_cache_dir / embedding_model).resolve()

    @property
    def ai_workspace_file(self) -> Path:
        """Path to the workspace registry file for a specific workspace."""
        return self.ai_cache_dir / WORKSPACE_REGISTRY_FILENAME

    def ensure_paths(self) -> None:
        """Ensure the root cache directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure_ai_paths(self) -> None:
        """Ensure the AI cache directory exists."""
        self.ai_cache_dir.mkdir(parents=True, exist_ok=True)
