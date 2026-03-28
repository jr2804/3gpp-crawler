"""LightRAG integration for 3gpp-ai.

This package provides a thin wrapper around LightRAG with:
- Multi-provider LLM and embedding support (ollama, openai, zhipu, jina, hf, etc.)
- File-based or pg0-backed storage
- Async context manager pattern
- TDoc document processing with docling extraction

Supported providers:
- LLM: ollama, openai, zhipu, hf, lollms, azure_openai, nvidia_openai
- Embedding: ollama, openai, zhipu, jina, hf, siliconcloud

Example:
    >>> import asyncio
    >>> async def main():
    ...     async with TDocRAG() as rag:
    ...         await rag.insert("TDoc S4-250001 about TS 26.444")
    ...         result = await rag.query("What TDocs mention TS 26.444?")
    ...         print(result)
    >>> asyncio.run(main())
"""

from .config import (
    DatabaseConfig,
    EmbeddingConfig,
    LightRAGConfig,
    LLMConfig,
    QueryMode,
    StorageBackend,
)
from .metadata import RAGMetadata, create_metadata_from_dict, enrich_text
from .pg0_manager import Pg0Error, Pg0Manager
from .processor import DocumentProcessor, ProcessingResult, ProcessingResultStatus, TDocProcessor
from .rag import TDocRAG
from .seeder import EntitySeed, EntitySeeder, EntityType
from .shared_storage import SharedNanoVectorDBStorage, WorkspaceIndex, initialize_shared_storage

__all__ = [
    "DatabaseConfig",
    "DocumentProcessor",
    "EmbeddingConfig",
    "EntitySeed",
    "EntitySeeder",
    "EntityType",
    "LLMConfig",
    "LightRAGConfig",
    "Pg0Error",
    "Pg0Manager",
    "ProcessingResult",
    "ProcessingResultStatus",
    "QueryMode",
    "RAGMetadata",
    "SharedNanoVectorDBStorage",
    "StorageBackend",
    "TDocProcessor",
    "TDocRAG",
    "WorkspaceIndex",
    "create_metadata_from_dict",
    "enrich_text",
    "initialize_shared_storage",
]
