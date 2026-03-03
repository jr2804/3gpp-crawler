"""ServiceContainer for centralized dependency management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lancedb
import requests

from tdoc_crawler.config import CacheManager
from tdoc_crawler.config.service import ConfigService
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.database.tdocs import TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)


class ServiceContainer:
    """Manages lifecycle and resolution of core services.

    The container provides centralized access to core services while
    maintaining full backward compatibility with existing code patterns.
    Services are created lazily on first access and cached for reuse.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        name: str = "default"
    ) -> None:
        """Initialize container with optional cache directory.

        Args:
            cache_dir: Optional cache directory path. If None, uses default
                       from CacheManager or TDC_CACHE_DIR environment variable.
            name: Container identifier for multi-container scenarios.
        """
        self._cache_dir = cache_dir
        self._name = name
        self._cache_manager: CacheManager | None = None
        self._config_service: ConfigService | None = None
        self._session: requests.Session | None = None
        self._db_instances: dict[str, Any] = {}

    @property
    def cache_manager(self) -> CacheManager:
        """Get the registered cache manager, creating if necessary.

        Returns:
            CacheManager instance registered in container.

        Raises:
            RuntimeError: If cache manager cannot be created or registered.
        """
        if self._cache_manager is None:
            self._cache_manager = CacheManager(
                root_path=self._cache_dir,
                name=self._name,
                ensure_paths=True
            )
            self._cache_manager.register()
            logger.debug(f"Created and registered CacheManager: {self._name}")
        return self._cache_manager

    def get_cache_manager(self) -> CacheManager:
        """Get the CacheManager instance managed by this container.

        Convenience method alias for the ``cache_manager`` property.

        Returns:
            CacheManager instance registered in container.
        """
        return self.cache_manager

    def ensure_paths(self) -> None:
        """Ensure all cache directories managed by this container exist.

        Creates the root cache directory and the AI cache directory if they
        do not already exist. Idempotent - safe to call multiple times.
        """
        self.cache_manager.ensure_paths()
        self.cache_manager.ensure_ai_paths()

    @property
    def config(self) -> ConfigService:
        """Get ConfigService providing unified access to all configuration.

        Returns:
            ConfigService instance bound to this container's cache manager name.
        """
        if self._config_service is None:
            # Ensure cache manager is initialized before ConfigService uses it
            _ = self.cache_manager
            self._config_service = ConfigService(
                cache_manager_name=self._name,
                cache_dir=self._cache_dir,
            )
        return self._config_service

    def get_tdoc_db(self) -> TDocDatabase:
        """Get TDoc database instance.

        Returns:
            TDocDatabase instance configured with container's cache manager.

        Raises:
            RuntimeError: If cache manager not available.
            IOError: If database file cannot be accessed.
        """
        key = "tdoc"
        if key not in self._db_instances:
            self._db_instances[key] = TDocDatabase(self.cache_manager.db_file)
        return self._db_instances[key]

    def get_spec_db(self) -> SpecDatabase:
        """Get Spec database instance.

        Returns:
            SpecDatabase instance configured with container's cache manager.
        """
        key = "spec"
        if key not in self._db_instances:
            self._db_instances[key] = SpecDatabase(self.cache_manager.db_file)
        return self._db_instances[key]

    def get_meeting_db(self) -> MeetingDatabase:
        """Get Meeting database instance.

        Returns:
            MeetingDatabase instance configured with container's cache manager.
        """
        key = "meeting"
        if key not in self._db_instances:
            self._db_instances[key] = MeetingDatabase(self.cache_manager.db_file)
        return self._db_instances[key]

    def get_ai_db(self, embedding_model: str | None = None) -> lancedb.db.LanceDBConnection:
        """Get LanceDB connection for AI storage.

        The connection is created at the correct path based on the embedding model:
        ``{ai_cache_dir}/{provider}/{model}/lancedb/``.

        For example, with model ``openai/text-embedding-3-small`` the path becomes:
        ``~/.tdoc-crawler/.ai/openai/text-embedding-3-small/lancedb/``.

        Args:
            embedding_model: Embedding model identifier in ``<provider>/<model>`` format.
                If None, uses the default from ``tdoc_crawler.ai.config``.

        Returns:
            LanceDB connection at the model-specific path.
        """
        from tdoc_crawler.ai.config import DEFAULT_EMBEDDING_MODEL

        resolved_model = embedding_model or DEFAULT_EMBEDDING_MODEL
        key = f"ai_db:{resolved_model}"
        if key not in self._db_instances:
            store_path = self.cache_manager.ai_embed_dir(resolved_model) / "lancedb"
            store_path.mkdir(parents=True, exist_ok=True)
            self._db_instances[key] = lancedb.connect(str(store_path))
            logger.debug(f"Created LanceDB connection at: {store_path}")
        return self._db_instances[key]

    def get_session(self) -> requests.Session:
        """Get HTTP session with caching.

        Sessions are cached and reused across multiple calls.
        Uses cache manager from container for HTTP cache storage.

        Returns:
            requests.Session configured with hishel caching.
        """
        if self._session is None:
            self._session = create_cached_session(
                cache_manager_name=self._name
            )
            logger.debug(f"Created HTTP session for container: {self._name}")
        return self._session

    def close(self) -> None:
        """Close container and release resources.

        Closes HTTP session if opened. Safe to call multiple times.
        Database connections are closed via context manager.
        """
        if self._session is not None:
            self._session.close()
            self._session = None
            logger.debug("Closed HTTP session")

        # Close any open database connections
        for key, db in self._db_instances.items():
            if hasattr(db, 'close'):
                try:
                    db.close()
                    logger.debug(f"Closed database: {key}")
                except Exception as e:
                    logger.warning(f"Failed to close database {key}: {e}")
        self._db_instances.clear()

        # Clear cache manager reference
        self._cache_manager = None

    def __enter__(self) -> ServiceContainer:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()


__all__ = ["ServiceContainer"]
