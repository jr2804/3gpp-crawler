"""LightRAG wrapper for 3gpp-ai with multi-provider support.

This module provides a thin wrapper around LightRAG with:
- Multi-provider LLM and embedding support (ollama, openai, zhipu, jina, hf, etc.)
- File-based or pg0-backed storage
- Async context manager pattern for proper lifecycle management
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any

# Monkey-patch zhipu functions to filter out base_url
import lightrag.llm.zhipu as zhipu_module
from lightrag import LightRAG, QueryParam
from lightrag.kg import STORAGES
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.hf import hf_embed, hf_model_complete
from lightrag.llm.jina import jina_embed
from lightrag.llm.ollama import ollama_embed, ollama_model_complete
from lightrag.llm.openai import openai_complete, openai_embed
from lightrag.llm.zhipu import zhipu_complete, zhipu_embedding
from lightrag.utils import EmbeddingFunc
from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.logging import get_logger

from .config import LightRAGConfig, QueryMode, StorageBackend
from .pg0_manager import Pg0Manager
from .shared_storage import WorkspaceIndex

# Patch zhipu_complete_if_cache
original_zhipu_complete_if_cache = zhipu_module.zhipu_complete_if_cache


@wraps(original_zhipu_complete_if_cache)
async def patched_zhipu_complete_if_cache(
    prompt: str,
    model: str = "glm-4-flashx",
    api_key: str | None = None,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    enable_cot: bool = False,
    **kwargs: Any,
) -> Any:
    # Remove unsupported kwargs including base_url
    if history_messages is None:
        history_messages = []
    kwargs = {k: v for k, v in kwargs.items() if k not in ["hashing_kv", "keyword_extraction", "base_url"]}
    return await original_zhipu_complete_if_cache(
        prompt=prompt,
        model=model,
        api_key=api_key,
        system_prompt=system_prompt,
        history_messages=history_messages,
        enable_cot=enable_cot,
        **kwargs,
    )


# Patch zhipu_embedding
original_zhipu_embedding = zhipu_module.zhipu_embedding


@wraps(original_zhipu_embedding)
async def patched_zhipu_embedding(
    texts: list[str],
    model: str = "embedding-3",
    api_key: str | None = None,
    **kwargs: Any,
) -> Any:
    # Remove unsupported kwargs including base_url
    kwargs = {k: v for k, v in kwargs.items() if k not in ["base_url"]}
    return await original_zhipu_embedding(
        texts=texts,
        model=model,
        api_key=api_key,
        **kwargs,
    )


# Apply the patches
zhipu_module.zhipu_complete_if_cache = patched_zhipu_complete_if_cache
zhipu_module.zhipu_embedding = patched_zhipu_embedding

STORAGES["SharedNanoVectorDBStorage"] = "threegpp_ai.lightrag.shared_storage"
logger = get_logger(__name__)


@dataclass(frozen=True)
class ProviderConfig:
    """Provider function mapping with optional kwargs."""

    complete_func: Callable | None = None
    embed_func: Callable | None = None


@dataclass(frozen=True)
class ProviderAlias:
    """Provider alias with optional base URL override."""

    canonical: str
    base_url: str | None = None


PROVIDERS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(complete_func=ollama_model_complete, embed_func=ollama_embed),
    "openai": ProviderConfig(complete_func=openai_complete, embed_func=openai_embed),
    "zhipu": ProviderConfig(complete_func=zhipu_complete, embed_func=zhipu_embedding),
    "hf": ProviderConfig(complete_func=hf_model_complete, embed_func=hf_embed),
    "jina": ProviderConfig(embed_func=jina_embed),
}

PROVIDER_ALIASES: dict[str, ProviderAlias] = {
    "zai": ProviderAlias(canonical="openai", base_url="https://api.z.ai/api/paas/v4"),
    "zai-coding-plan": ProviderAlias(canonical="openai", base_url="https://api.z.ai/api/coding/paas/v4"),
    "openrouter": ProviderAlias(canonical="openai", base_url="https://openrouter.ai/api/v1"),
    "nvidia": ProviderAlias(canonical="openai", base_url="https://integrate.api.nvidia.com/v1/"),
}


def _resolve_provider(provider: str) -> str:
    """Resolve provider alias to canonical name."""
    if provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider].canonical
    if provider not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS.keys()))
        raise ValueError(f"Unsupported provider '{provider}'. Available: {available}")
    return provider


def _parse_provider(model_string: str) -> tuple[str, str]:
    """Parse provider/model from <provider>/<model> format."""
    if "/" in model_string:
        parts = model_string.split("/", 1)
        return parts[0], parts[1]
    return "", model_string


def _get_provider(provider: str) -> ProviderConfig:
    """Get provider config by name."""
    return PROVIDERS[_resolve_provider(provider)]


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

    def __init__(self, config: LightRAGConfig | None = None) -> None:
        self.config = config or LightRAGConfig.from_env()
        self._rag: LightRAG | None = None
        self._pg0_manager = None
        self._workspace_index: WorkspaceIndex | None = None
        self._working_dir: Path | None = None

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

        # Prepare working directory using CacheManager (single source of truth)
        # Structure: ~/.3gpp-crawler/lightrag/{embedding_model}/
        # LightRAG will create workspace subdirectory internally
        manager = resolve_cache_manager()
        embedding_model_safe = self.config.embedding.model.replace(":", "-").replace("/", "-")
        working_dir = manager.ai_embed_dir(embedding_model_safe)
        working_dir.mkdir(parents=True, exist_ok=True)
        self._working_dir = working_dir
        logger.info("Using working directory: %s", working_dir)

        # Initialize shared storage if enabled
        if self.config.shared_storage:
            logger.info("Shared storage enabled - embeddings will be deduplicated across workspaces")
            # Initialize workspace index for this workspace
            self._workspace_index = WorkspaceIndex(
                workspace_name=workspace,
                working_dir=working_dir,
            )

        # Determine storage backend
        if self.config.database.backend == StorageBackend.PG0 and self._pg0_manager:
            kv_storage = "PGKVStorage"
            vector_storage = "PGVectorStorage"
            doc_status_storage = "PGDocStatusStorage"
            storage_label = "pg0"
        elif self.config.shared_storage:
            # Use custom shared storage classes
            kv_storage = "JsonKVStorage"  # Keep KV storage workspace-specific for now
            vector_storage = "SharedNanoVectorDBStorage"  # Use shared vector storage
            doc_status_storage = "JsonDocStatusStorage"
            storage_label = "shared file-based"
        else:
            kv_storage = "JsonKVStorage"
            vector_storage = "NanoVectorDBStorage"
            doc_status_storage = "JsonDocStatusStorage"
            storage_label = "file-based"

        embed_provider, embed_model_name = _parse_provider(self.config.embedding.model)
        llm_provider, llm_model_name = _parse_provider(self.config.llm.model)

        embed_config = _get_provider(embed_provider)
        llm_config = _get_provider(llm_provider)

        embed_kwargs = self._build_provider_kwargs(embed_provider, embed_model_name, is_embedding=True)
        llm_kwargs = self._build_provider_kwargs(llm_provider, llm_model_name)

        async def wrapped_embed_func(texts: list[str], **kwargs: Any) -> list[list[float]]:
            return await embed_config.embed_func(texts, **embed_kwargs, **kwargs)  # type: ignore[call-arg]

        # Probe the model to detect the actual embedding dimension — never assume.
        probe = await wrapped_embed_func(["probe"])
        embed_dim = len(probe[0])
        logger.info("Detected embedding dimension: %d for model '%s'", embed_dim, self.config.embedding.model)

        embedding_func = EmbeddingFunc(embedding_dim=embed_dim, func=wrapped_embed_func)

        self._rag = LightRAG(
            working_dir=str(working_dir),
            workspace=workspace,
            llm_model_func=llm_config.complete_func,
            llm_model_name=llm_model_name,
            llm_model_kwargs=llm_kwargs,
            embedding_func=embedding_func,
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

        try:
            await self._rag.ainsert(text, **kwargs)
        except TypeError as exc:
            message = str(exc)
            if "unexpected keyword argument" in message and kwargs:
                logger.warning("LightRAG ainsert does not accept kwargs in this version; retrying without kwargs")
                await self._rag.ainsert(text)
                return
            raise

    async def query(
        self,
        query: str,
        mode: QueryMode | str | None = None,
        include_citation_hints: bool = True,
        **kwargs: Any,
    ) -> str:
        """Query the knowledge graph.

        Args:
            query: Query string
            mode: Query mode (naive, local, global, hybrid, mix, bypass).
                Defaults to config.default_query_mode.
            include_citation_hints: Whether to instruct LLM to include element-aware citations.
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

        query_text = query
        if include_citation_hints:
            query_text = (
                f"{query}\n\n"
                "When relevant, cite source context with available metadata fields "
                "such as element type (table/figure/equation/text), element_id, page, and section."
            )

        query_param_kwargs: dict[str, Any] = {"mode": mode.value}

        try:
            return await self._rag.aquery(
                query_text,
                param=QueryParam(**query_param_kwargs),
                **kwargs,
            )
        except KeyError as exc:
            if exc.args and exc.args[0] == "hashing_kv":
                logger.warning("Query skipped because workspace has no indexed chunks yet")
                return ""
            raise

    @property
    def is_started(self) -> bool:
        """Check if LightRAG is currently running."""
        return self._rag is not None

    @property
    def workspace_index(self) -> WorkspaceIndex | None:
        """Get the workspace index for tracking chunks."""
        return self._workspace_index

    @property
    def working_dir(self) -> Path | None:
        """Get the working directory."""
        return self._working_dir

    def _build_provider_kwargs(self, provider: str, model_name: str, is_embedding: bool = False) -> dict[str, Any]:
        """Build provider-specific kwargs for LLM/embedding functions."""
        config = self.config.embedding if is_embedding else self.config.llm

        # Resolve alias to canonical provider name
        canonical_provider = _resolve_provider(provider)

        if canonical_provider == "ollama":
            # Ollama uses different kwargs for embedding vs completion
            kwargs = {"host": config.api_base}
            if is_embedding:
                kwargs["embed_model"] = model_name
            return kwargs
        if canonical_provider == "openai":
            # LightRAG's openai_complete expects base_url, not api_base
            # Check for alias-specific base URL override
            base_url = config.api_base
            if provider in PROVIDER_ALIASES and PROVIDER_ALIASES[provider].base_url:
                base_url = PROVIDER_ALIASES[provider].base_url
            return {"api_key": config.api_key, "base_url": base_url}
        if canonical_provider == "zhipu":
            # zhipu_complete_if_cache only accepts api_key, not base_url
            return {"api_key": config.api_key}
        if canonical_provider == "jina":
            return {"api_key": config.api_key}
        return {}
