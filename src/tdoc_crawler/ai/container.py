"""AI Service Container - Singleton for AI module dependencies.

This module provides a centralized container for AI services (AiConfig, AiStorage,
EmbeddingsManager) following the Dependency Injection patterns defined in
specs/001-di-refactoring-plan/.

The container implements lazy initialization and singleton pattern to ensure:
- Single LanceDB connection per session
- Correct cache path including provider/model subdirectory
- Easy testing through dependency injection
"""

from __future__ import annotations

from typing import Any

from sentence_transformers import SentenceTransformer

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.ai.operations.embeddings import EmbeddingsManager
from tdoc_crawler.ai.storage import AiStorage


class AiServiceContainer:
    """
    Singleton container for AI services.

    Provides centralized access to AiConfig, AiStorage, and EmbeddingsManager
    with lazy initialization. This ensures single instantiation and correct
    cache path resolution.

    Usage:
        # Get the singleton instance
        container = AiServiceContainer.get_instance()

        # Get services (lazy initialized)
        config = container.get_config()
        storage = container.get_storage()
        embeddings = container.get_embeddings_manager()

        # Or use convenience method
        storage = container.get_ai_storage()
    """

    _instance: AiServiceContainer | None = None
    _config: AiConfig | None = None
    _storage: AiStorage | None = None
    _embeddings_manager: EmbeddingsManager | None = None

    def __new__(cls) -> AiServiceContainer:
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize instance attributes
            cls._instance._config = None
            cls._instance._storage = None
            cls._instance._embeddings_manager = None
        return cls._instance

    def get_config(self) -> AiConfig:
        """Get the AI configuration singleton.

        Loads configuration from environment variables using AiConfig.from_env().

        Returns:
            AiConfig singleton instance.
        """
        if self._config is None:
            self._config = AiConfig.from_env()
        return self._config

    def get_embeddings_manager(self) -> EmbeddingsManager:
        """Get the embeddings manager singleton.

        Creates EmbeddingsManager with the shared config and storage.
        Note: Storage must be initialized before calling this method.

        Returns:
            EmbeddingsManager singleton instance.
        """
        if self._embeddings_manager is None:
            config = self.get_config()
            storage = self.get_storage()
            self._embeddings_manager = EmbeddingsManager(config=config, storage=storage)
        return self._embeddings_manager

    def get_storage(self) -> AiStorage:
        """Get the AI storage singleton.

        Creates AiStorage with the correct cache path (including provider/model
        subdirectory) obtained from AiConfig.

        Returns:
            AiStorage singleton instance.
        """
        if self._storage is None:
            config = self.get_config()
            # Load dimension directly from model to avoid circular dependency
            # with get_embeddings_manager() which requires storage
            dimension = self._load_embedding_dimension()
            # AiConfig.ai_cache_dir already includes the provider/model subdirectory
            # when embedding_model is set (see config.py lines 148-152)
            self._storage = AiStorage(config.ai_cache_dir, embedding_dimension=dimension)
        return self._storage

    # Aliases for compatibility with main ServiceContainer design
    def get_ai_config(self) -> AiConfig:
        """Alias for get_config() - compatibility with main ServiceContainer."""
        return self.get_config()

    def get_ai_storage(self) -> AiStorage:
        """Alias for get_storage() - compatibility with main ServiceContainer."""
        return self.get_storage()

    def get_embeddings(self) -> EmbeddingsManager:
        """Alias for get_embeddings_manager() - compatibility with main ServiceContainer."""
        return self.get_embeddings_manager()

    def close(self) -> None:
        """Close the container and release resources.

        Resets all singleton instances. Safe to call multiple times.
        """
        self._storage = None
        self._embeddings_manager = None
        self._config = None

    def __enter__(self) -> AiServiceContainer:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance.

        This is primarily used for testing to ensure each test starts
        with a fresh container. After calling this method, the next
        call to get_instance() will create a new container instance.
        """
        cls._instance = None

    @classmethod
    def get_instance(cls) -> AiServiceContainer:
        """Get the singleton container instance.

        Returns:
            AiServiceContainer singleton instance.
        """
        return cls()

    @classmethod
    def reset_for_testing(cls) -> None:
        """Reset the singleton for testing purposes.

        WARNING: Only use in tests, not in production code.
        """
        cls._instance = None

    def _load_embedding_dimension(self) -> int:
        """Load the embedding dimension from the configured model.

        This is a helper method to avoid circular dependencies between
        get_storage() and get_embeddings_manager().

        Returns:
            The embedding dimension for the configured model.
        """
        config = self.get_config()

        model = SentenceTransformer(config.embedding_model)
        dimension = model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError(f"Model '{config.embedding_model}' did not report an embedding dimension")
        return dimension


# Convenience functions for backward compatibility
def get_ai_config() -> AiConfig:
    """Get AI configuration singleton.

    Returns:
        AiConfig singleton instance.
    """
    return AiServiceContainer.get_instance().get_config()


def get_ai_storage() -> AiStorage:
    """Get AI storage singleton.

    Returns:
        AiStorage singleton instance.
    """
    return AiServiceContainer.get_instance().get_storage()


def get_embeddings_manager() -> EmbeddingsManager:
    """Get embeddings manager singleton.

    Returns:
        EmbeddingsManager singleton instance.
    """
    return AiServiceContainer.get_instance().get_embeddings_manager()


__all__ = [
    "AiServiceContainer",
    "get_ai_config",
    "get_ai_storage",
    "get_embeddings_manager",
]
