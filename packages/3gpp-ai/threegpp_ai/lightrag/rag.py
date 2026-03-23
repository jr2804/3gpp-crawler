"""LightRAG wrapper for 3gpp-ai with Ollama integration.

This module provides a thin wrapper around LightRAG with:
- Ollama LLM and embedding support
- File-based or pg0-backed storage
- Async context manager pattern for proper lifecycle management
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.ollama import ollama_embed, ollama_model_complete

from .config import LightRAGConfig, QueryMode, StorageBackend
from .pg0_manager import Pg0Manager

logger = logging.getLogger(__name__)

# Embedding dimensions by model name ( Ollama API doesn't return this)
EMBEDDING_DIMENSIONS: dict[str, int] = {
    "qwen3-embedding:0.6b": 1024,
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
}


def _get_embedding_dimension(model_name: str) -> int:
    """Get embedding dimension for a model.

    Returns dimension from known models, or defaults to 1024.
    """
    return EMBEDDING_DIMENSIONS.get(model_name, 1024)


class TDocRAG:
    """Thin wrapper around LightRAG with Ollama and optional pg0 support.

    This class manages the LightRAG lifecycle and provides a simple interface
    for inserting documents and querying the knowledge graph.

    Args:
        config: LightRAG configuration. If None, uses defaults from env
            or LightRAGConfig class defaults.

    Example:
        >>> import asyncio
        >>> async def main():
        ...     async with TDocRAG() as rag:
        ...         await rag.insert("TDoc S4-250001 about TS 26.444")
        ...         result = await rag.query("What TDocs mention TS 26.444?")
        ...         print(result)
        >>> asyncio.run(main())
    """

    def __init__(self, config: LightRAGConfig | None = None):
        self.config = config or LightRAGConfig()
        self._rag: LightRAG | None = None
        self._pg0_manager = None

    async def __aenter__(self) -> TDocRAG:
        """Async context manager entry - starts LightRAG."""
        await self.start()
        return self

    async def __aexit__(self, _: Any, __: Any, ___: Any) -> None:
        """Async context manager exit - stops LightRAG."""
        await self.stop()

    async def start(self, workspace: str | None = None) -> None:
        """Start pg0 (if enabled) and initialize LightRAG.

        Args:
            workspace: Workspace name for isolation (defaults to config.workspace)
        """
        workspace = workspace or self.config.workspace

        # Start pg0 if configured
        if self.config.database.backend == StorageBackend.PG0:
            self._pg0_manager = Pg0Manager(
                instance_name=self.config.database.pg0_instance_name,
                port=self.config.database.pg0_port,
                database=self.config.database.pg0_database,
            )
            self._pg0_manager.start()
            logger.info("Using pg0 at %s", self._pg0_manager.uri)

        # Prepare working directory
        working_dir = Path(self.config.working_dir).expanduser() / workspace
        working_dir.mkdir(parents=True, exist_ok=True)

        # Determine storage backend
        if self.config.database.backend == StorageBackend.PG0 and self._pg0_manager:
            kv_storage = "PGKVStorage"
            vector_storage = "PGVectorStorage"
            doc_status_storage = "PGDocStatusStorage"
            storage_label = "pg0"
        else:
            kv_storage = "JsonKVStorage"
            vector_storage = "NanoVectorDBStorage"
            doc_status_storage = "JsonDocStatusStorage"
            storage_label = "file-based"

        # Get embedding dimension for model
        embed_dim = _get_embedding_dimension(self.config.embedding.model)

        # Create embedding function with proper dimension attribute
        async def embed_func(texts: list[str], **kwargs: Any) -> list[list[float]]:
            return await ollama_embed(
                texts,
                embed_model=self.config.embedding.model,
                host=self.config.embedding.host,
                **kwargs,
            )

        # LightRAG requires embedding_dim on the function
        embed_func.embedding_dim = embed_dim

        # Initialize LightRAG
        self._rag = LightRAG(
            working_dir=str(working_dir),
            workspace=workspace,
            # LLM configuration
            llm_model_func=ollama_model_complete,
            llm_model_name=self.config.llm.model,
            llm_model_kwargs={
                "host": self.config.llm.host,
                "api_key": self.config.llm.api_key,
            },
            # Embedding configuration
            embedding_func=embed_func,
            # Storage backend
            kv_storage=kv_storage,
            vector_storage=vector_storage,
            doc_status_storage=doc_status_storage,
            graph_storage="NetworkXStorage",
        )

        await self._rag.initialize_storages()
        await initialize_pipeline_status()
        logger.info(
            "LightRAG started for workspace '%s' with %s storage",
            workspace,
            storage_label,
        )

    async def stop(self) -> None:
        """Finalize LightRAG and stop pg0."""
        if self._rag:
            await self._rag.finalize_storages()
            logger.info("LightRAG finalized")

        if self._pg0_manager:
            self._pg0_manager.stop()
            self._pg0_manager = None

    async def insert(self, text: str, **kwargs: Any) -> None:
        """Insert document text into the knowledge graph.

        Args:
            text: Document text to insert
            **kwargs: Additional arguments passed to rag.ainsert()
        """
        if not self._rag:
            raise RuntimeError("TDocRAG not started. Call start() first.")
        await self._rag.ainsert(text, **kwargs)

    async def query(
        self,
        query: str,
        mode: QueryMode | str | None = None,
        **kwargs: Any,
    ) -> str:
        """Query the knowledge graph.

        Args:
            query: Query string
            mode: Query mode (naive, local, global, hybrid, mix, bypass).
                Defaults to config.default_query_mode.
            **kwargs: Additional arguments passed to rag.aquery()

        Returns:
            Query result string
        """
        if not self._rag:
            raise RuntimeError("TDocRAG not started. Call start() first.")

        # Resolve mode
        if mode is None:
            mode = self.config.default_query_mode
        elif isinstance(mode, str):
            mode = QueryMode(mode)

        return await self._rag.aquery(
            query,
            param=QueryParam(mode=mode.value, model_func=ollama_model_complete),
            **kwargs,
        )

    @property
    def is_started(self) -> bool:
        """Check if LightRAG is currently running."""
        return self._rag is not None
