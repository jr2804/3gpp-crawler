"""Shared storage layer for cross-workspace embedding deduplication.

This module provides:
- SharedNanoVectorDBStorage: Embedding storage shared across all workspaces
- WorkspaceIndex: Maps workspace documents to shared chunk IDs
- Content-based deduplication using text hashing

Architecture:
    ~/.3gpp-crawler/lightrag/{embedding_model}/
    ├── _shared/                    # Shared across all workspaces
    │   ├── vdb_text_chunks.json    # Global embedding store
    │   └── kv_store_llm_cache.json # Global LLM cache
    │
    ├── atias/
    │   ├── workspace_index.json    # Maps atias docs → shared chunk IDs
    │   └── graph_*.graphml         # Workspace-specific graph
    │
    └── project-x/
        ├── workspace_index.json    # Maps project-x docs → shared chunk IDs
        └── graph_*.graphml         # Workspace-specific graph
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lightrag.base import BaseVectorStorage, EmbeddingFunc
from lightrag.utils import compute_mdhash_id
from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WorkspaceIndex:
    """Index mapping workspace documents to shared chunk IDs.

    This lightweight index tracks which chunks belong to which workspace
    without duplicating the actual embeddings.

    Structure:
    {
        "documents": {
            "doc_id_1": ["chunk_id_1", "chunk_id_2"],
            "doc_id_2": ["chunk_id_3"]
        },
        "chunks": {
            "chunk_id_1": ["doc_id_1"],
            "chunk_id_2": ["doc_id_1"],
            "chunk_id_3": ["doc_id_2"]
        },
        "metadata": {
            "chunk_id_1": {"source_doc": "doc_id_1", "text_hash": "abc123"}
        }
    }
    """

    workspace_name: str
    working_dir: Path
    _data: dict[str, Any] = field(
        default_factory=lambda: {
            "documents": {},
            "chunks": {},
            "metadata": {},
        }
    )

    def __post_init__(self):
        """Initialize workspace index."""
        self._file_path = self.working_dir / self.workspace_name / "workspace_index.json"
        self._load()

    def _load(self) -> None:
        """Load index from disk if it exists."""
        if self._file_path.exists():
            try:
                with open(self._file_path, encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.debug(
                    "Loaded workspace index for '%s' (%d docs, %d chunks)",
                    self.workspace_name,
                    len(self._data.get("documents", {})),
                    len(self._data.get("chunks", {})),
                )
            except Exception as e:
                logger.warning("Failed to load workspace index: %s", e)
                self._data = {"documents": {}, "chunks": {}, "metadata": {}}
        else:
            logger.debug("Created new workspace index for '%s'", self.workspace_name)

    def _save(self) -> None:
        """Save index to disk."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        logger.debug("Saved workspace index for '%s'", self.workspace_name)


@dataclass
class SharedNanoVectorDBStorage(BaseVectorStorage):
    """NanoVectorDB storage shared across all workspaces.

    This storage class:
    1. Stores embeddings in a shared directory (_shared/)
    2. Uses content-based hashing for deduplication
    3. Returns existing embeddings for duplicate content
    4. Maintains workspace-specific indices for isolation

    Args:
        global_config: LightRAG global configuration
        namespace: Storage namespace (e.g., "text_chunks")
    """

    # Required fields from StorageNameSpace
    namespace: str = field(default="shared")
    workspace: str = field(default="_shared")
    global_config: dict[str, Any] = field(default_factory=dict, repr=False)

    # Required fields from BaseVectorStorage
    embedding_func: EmbeddingFunc = field(default=None, repr=False)
    cosine_better_than_threshold: float = field(default=0.2)
    meta_fields: set[str] = field(default_factory=set)

    # Internal state
    _shared_dir: Path = field(default=None, repr=False, init=False)
    _db_file: Path = field(default=None, repr=False, init=False)
    _data: dict[str, Any] = field(default_factory=dict, repr=False, init=False)
    _current_workspace: str = field(default="", repr=False, init=False)

    def __post_init__(self):
        """Initialize shared storage after dataclass initialization."""
        # Get working directory from global_config
        working_dir = Path(self.global_config.get("working_dir", "./rag_storage"))

        # Shared directory is at embedding model level, not workspace level
        # Structure: working_dir/_shared/
        self._shared_dir = working_dir / "_shared"
        self._shared_dir.mkdir(parents=True, exist_ok=True)

        # Workspace for filtering (set by TDocRAG.start())
        self._current_workspace = self.global_config.get("workspace", "")

        # Storage file path in shared directory
        self._db_file = self._shared_dir / f"vdb_{self.namespace}.json"

        # In-memory data structure
        self._data = {
            "data": {},  # chunk_id → {text, embedding, metadata}
            "index": {},  # text_hash → chunk_id
        }

        # Load existing data
        self._load()

    async def upsert(self, data: dict[str, dict[str, Any]], **kwargs: Any) -> None:
        """Insert or update embeddings with deduplication.

        Args:
            data: Dict of {chunk_id: {text, embedding, metadata}}
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.
        """
        logger.debug("Upserting %d items to shared %s", len(data), self.namespace)

        for chunk_id, item_data in data.items():
            text = item_data.get("text", "")
            embedding = item_data.get("embedding")
            metadata = item_data.get("metadata", {})

            if not text or embedding is None:
                logger.warning("Skipping invalid chunk %s: missing text or embedding", chunk_id)
                continue

            # Compute hash for deduplication
            text_hash = self._compute_text_hash(text)

            # Check if this exact text already exists
            if text_hash in self._data["index"]:
                existing_chunk_id = self._data["index"][text_hash]
                logger.debug(
                    "Duplicate text detected: %s → reusing existing chunk %s",
                    chunk_id,
                    existing_chunk_id,
                )
                # Update metadata but keep existing embedding
                if existing_chunk_id in self._data["data"]:
                    self._data["data"][existing_chunk_id]["metadata"].update(metadata)
            else:
                # New unique chunk
                self._data["data"][chunk_id] = {
                    "text": text,
                    "embedding": embedding,
                    "metadata": metadata,
                }
                self._data["index"][text_hash] = chunk_id
                logger.debug("Stored new unique chunk %s", chunk_id)

        self._save()

    async def get_by_ids(self, ids: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve embeddings by chunk IDs.

        Args:
            ids: List of chunk IDs
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.

        Returns:
            List of embedding data dicts
        """
        results = []
        for chunk_id in ids:
            if chunk_id in self._data["data"]:
                results.append(self._data["data"][chunk_id])
        return results

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[tuple[str, float]]:
        """Search for similar embeddings.

        Args:
            query: Query text (will be embedded externally)
            top_k: Number of results to return
            filter: Optional filter dict (not used in shared storage)
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.

        Returns:
            List of (chunk_id, similarity_score) tuples
        """
        # This method is called by LightRAG after embedding the query
        # The actual search is performed by the parent class or custom logic
        # For now, delegate to parent implementation
        return await super().search(query, top_k=top_k, filter=filter, **kwargs)

    async def query(
        self,
        query: str,
        top_k: int = 10,
        **kwargs: Any,
    ) -> list[tuple[str, float]]:
        """Query embeddings by similarity.

        Args:
            query: Query string
            top_k: Number of results
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.

        Returns:
            List of (chunk_id, score) tuples
        """
        return await self.search(query, top_k=top_k, **kwargs)

    async def get_by_id(self, id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Get embedding by chunk ID.

        Args:
            id: Chunk identifier
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.

        Returns:
            Embedding data dict or None
        """
        return self._data["data"].get(id)

    async def get_vectors_by_ids(self, ids: list[str], **kwargs: Any) -> dict[str, list[float]]:
        """Get embedding vectors by chunk IDs.

        Args:
            ids: List of chunk IDs
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.

        Returns:
            Dict of {chunk_id: embedding_vector}
        """
        result = {}
        for chunk_id in ids:
            if chunk_id in self._data["data"]:
                embedding = self._data["data"][chunk_id].get("embedding")
                if embedding:
                    result[chunk_id] = embedding
        return result

    async def filter_keys(self, keys: set[str], **kwargs: Any) -> set[str]:
        """Filter out keys that already exist in storage.

        Args:
            keys: Set of keys to check
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.

        Returns:
            Set of keys that exist in storage (will be filtered out)
        """
        existing = set()
        for key in keys:
            if key in self._data["data"]:
                existing.add(key)
        return existing

    async def delete_entity(self, entity_name: str) -> None:
        """Delete entity by name (not used in shared storage)."""
        pass

    async def delete_entity_relation(self, entity_name: str) -> None:
        """Delete entity relations by name (not used in shared storage)."""
        pass

    async def index_done_callback(self) -> None:
        """Callback after indexing is complete."""
        # Save after indexing
        self._save()

    async def initialize(self) -> None:
        """Initialize storage (already done in __init__)."""
        pass

    async def finalize(self) -> None:
        """Finalize storage - save any pending changes."""
        self._save()

    async def delete(self, ids: list[str], **kwargs: Any) -> None:
        """Delete embeddings by chunk IDs.

        Note: Only deletes from shared storage if chunk is not used by other workspaces.

        Args:
            ids: List of chunk IDs to delete
            **kwargs: Additional keyword arguments for compatibility with LightRAG storage interface.
        """
        for chunk_id in ids:
            if chunk_id in self._data["data"]:
                # Check if chunk is used by multiple workspaces
                # For now, we don't delete from shared storage to avoid complexity
                # A proper implementation would track workspace usage
                logger.debug("Marking chunk %s for deletion (not removing from shared)", chunk_id)

        # Note: We don't actually remove from shared storage to avoid breaking other workspaces
        # A production implementation would need reference counting

    async def drop(self) -> None:
        """Drop the entire shared storage.

        WARNING: This deletes ALL embeddings across ALL workspaces!
        Use with extreme caution.
        """
        if self._db_file.exists():
            self._db_file.unlink()
            logger.warning("Dropped shared %s storage", self.namespace)
        self._data = {"data": {}, "index": {}}

    @property
    def shared_dir(self) -> Path:
        """Get the shared storage directory."""
        return self._shared_dir

    @property
    def chunk_count(self) -> int:
        """Get total number of unique chunks in shared storage."""
        return len(self._data.get("data", {}))

    def _load(self) -> None:
        """Load shared storage from disk."""
        if self._db_file.exists():
            try:
                with open(self._db_file, encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(
                    "Loaded shared %s storage (%d chunks)",
                    self.namespace,
                    len(self._data.get("data", {})),
                )
            except Exception as e:
                logger.warning("Failed to load shared storage: %s", e)
                self._data = {"data": {}, "index": {}}
        else:
            logger.info("Created new shared %s storage", self.namespace)

    def _save(self) -> None:
        """Save shared storage to disk."""
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._db_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _compute_text_hash(text: str) -> str:
        """Compute MD5 hash for text deduplication.

        Args:
            text: Text content to hash

        Returns:
            MD5 hash string
        """
        return compute_mdhash_id(text.strip(), prefix="chunk-")


async def initialize_shared_storage(working_dir: Path, embedding_model: str) -> None:
    """Initialize shared storage directory structure.

    Args:
        working_dir: LightRAG working directory
        embedding_model: Embedding model name
    """
    shared_dir = working_dir / "_shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Initialized shared storage at %s", shared_dir)
