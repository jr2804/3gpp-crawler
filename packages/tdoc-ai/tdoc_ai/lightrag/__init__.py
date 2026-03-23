"""LightRAG integration for tdoc-ai.

This package provides a thin wrapper around LightRAG with:
- Ollama LLM and embedding support (qwen3-embedding:0.6b)
- File-based or pg0-backed storage
- Async context manager pattern
- TDoc document processing with kreuzberg extraction

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
from .processor import ProcessingResult, ProcessingResultStatus, TDocProcessor
from .rag import TDocRAG
from .seeder import EntitySeed, EntitySeeder, EntityType

__all__ = [
    "DatabaseConfig",
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
    "StorageBackend",
    "TDocProcessor",
    "TDocRAG",
    "create_metadata_from_dict",
    "enrich_text",
]
