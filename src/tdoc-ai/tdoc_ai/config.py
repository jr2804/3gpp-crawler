"""Configuration for the AI document processing pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import litellm
from pydantic import Field, field_validator, model_validator

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.models import BaseConfigModel

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LLM_MODEL = "openrouter/openrouter/free"

type Backend = Literal["torch", "onnx", "openvino"]

# Graph query level type
type GraphQueryLevel = Literal["simple", "medium", "advanced"]


def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


def _validate_model_identifier(value: str, field_name: str) -> str:
    if "/" not in value:
        msg = f"{field_name} must be in '<provider>/<model_name>' format"
        raise ValueError(msg)

    provider, model_name = value.split("/", 1)
    provider_normalized = provider.strip().lower()
    model_name_normalized = model_name.strip()

    if not provider_normalized:
        msg = f"{field_name} provider segment cannot be empty"
        raise ValueError(msg)
    if not model_name_normalized:
        msg = f"{field_name} model_name segment cannot be empty"
        raise ValueError(msg)

    supported_providers = set(litellm.LITELLM_CHAT_PROVIDERS + litellm.openai_compatible_providers)

    if provider_normalized not in supported_providers:
        msg = (
            f"{field_name} provider '{provider}' is not supported by litellm. "
            f"See https://docs.litellm.ai/docs/providers for the full list of {len(supported_providers)} supported providers."
        )
        raise ValueError(msg)

    return f"{provider_normalized}/{model_name_normalized}"


def _validate_embedding_model_format(value: str) -> str:
    """Validate embedding model - accepts any HuggingFace-style model ID.

    Unlike LLM models, embedding models via sentence-transformers don't require
    LiteLLM provider validation. Accepts formats like:
    - sentence-transformers/all-MiniLM-L6-v2
    - perplexity-ai/pplx-embed-v1-0.6b
    """
    if "/" not in value:
        msg = "embedding_model must be in '<provider>/<model_name>' format"
        raise ValueError(msg)

    provider, model_name = value.split("/", 1)
    provider_normalized = provider.strip().lower()
    model_name_normalized = model_name.strip()

    if not provider_normalized:
        msg = "embedding_model provider segment cannot be empty"
        raise ValueError(msg)
    if not model_name_normalized:
        msg = "embedding_model model_name segment cannot be empty"
        raise ValueError(msg)

    return f"{provider_normalized}/{model_name_normalized}"


class AiConfig(BaseConfigModel):
    """Configuration for the AI processing pipeline."""

    ai_cache_dir: Path | None = Field(None, description="Path to AI cache directory")

    embedding_model: str = Field(
        DEFAULT_EMBEDDING_MODEL,
        description="Embedding model in <provider>/<model_name> format",
    )
    embedding_backend: Backend = Field(
        "torch",
        description="Sentence-transformers backend (torch, onnx, openvino)",
    )
    max_chunk_size: int = Field(1000, ge=1, description="Max tokens per chunk")
    chunk_overlap: int = Field(100, ge=0, description="Token overlap between chunks")

    llm_model: str = Field(
        DEFAULT_LLM_MODEL,
        description="LLM model in <provider>/<model_name> format",
    )
    llm_api_base: str | None = Field(None, description="Override LLM API base URL")

    abstract_min_words: int = Field(150, ge=1, description="Minimum abstract word count")
    abstract_max_words: int = Field(250, ge=1, description="Maximum abstract word count")
    parallelism: int = Field(4, ge=1, le=32, description="Concurrent TDoc processing")

    graph_query_level: GraphQueryLevel = Field(
        "simple",
        description="Level of graph query answer generation (simple|medium|advanced)",
    )

    @classmethod
    def from_env(cls, **overrides: str | int | Path | None) -> AiConfig:
        """Create config from environment variables."""
        data: dict[str, str | int | Path | None] = {}

        # Set cache_manager_name for use in _resolve_paths validator
        if cache_manager_name := overrides.get("cache_manager_name"):
            data["cache_manager_name"] = cache_manager_name

        # NOTE: ai_cache_dir is NOT set here - it will be resolved in _resolve_paths
        # validator using ai_embed_dir(embedding_model) to include provider/model subdirectory

        if embedding_model := os.getenv("TDC_AI_EMBEDDING_MODEL"):
            data["embedding_model"] = embedding_model
        if embedding_backend := os.getenv("TDC_AI_EMBEDDING_BACKEND"):
            data["embedding_backend"] = embedding_backend
        if llm_model := os.getenv("TDC_AI_LLM_MODEL"):
            data["llm_model"] = llm_model
        if llm_api_base := os.getenv("TDC_AI_LLM_API_BASE"):
            data["llm_api_base"] = llm_api_base

        max_chunk_size = _env_int("TDC_AI_MAX_CHUNK_SIZE")
        if max_chunk_size is not None:
            data["max_chunk_size"] = max_chunk_size

        chunk_overlap = _env_int("TDC_AI_CHUNK_OVERLAP")
        if chunk_overlap is not None:
            data["chunk_overlap"] = chunk_overlap

        abstract_min_words = _env_int("TDC_AI_ABSTRACT_MIN_WORDS")
        if abstract_min_words is not None:
            data["abstract_min_words"] = abstract_min_words

        abstract_max_words = _env_int("TDC_AI_ABSTRACT_MAX_WORDS")
        if abstract_max_words is not None:
            data["abstract_max_words"] = abstract_max_words

        parallelism = _env_int("TDC_AI_PARALLELISM")
        if parallelism is not None:
            data["parallelism"] = parallelism

        if graph_query_level := os.getenv("TDC_GRAPH_QUERY_LEVEL"):
            data["graph_query_level"] = graph_query_level

        data.update(overrides)
        # Filter out None values to let defaults apply
        filtered_data = {k: v for k, v in data.items() if v is not None}
        return cls(**filtered_data)

    @model_validator(mode="after")
    def _resolve_paths(self) -> AiConfig:
        if self.ai_cache_dir is None:
            # Use CacheManager to resolve the embedding directory
            # e.g., ~/.tdoc-crawler/.ai/sentence-transformers/all-MiniLM-L6-v2
            # The ai_embed_dir method handles the provider/model subdirectory structure
            self.ai_cache_dir = resolve_cache_manager(self.cache_manager_name).ai_embed_dir(self.embedding_model)

        return self

    @model_validator(mode="after")
    def _validate_bounds(self) -> AiConfig:
        if self.abstract_max_words < self.abstract_min_words:
            msg = "abstract_max_words must be >= abstract_min_words"
            raise ValueError(msg)
        if self.chunk_overlap >= self.max_chunk_size:
            msg = "chunk_overlap must be less than max_chunk_size"
            raise ValueError(msg)
        return self

    @field_validator("embedding_model")
    @classmethod
    def _validate_embedding_model(cls, value: str) -> str:
        return _validate_embedding_model_format(value)

    @field_validator("embedding_backend")
    @classmethod
    def _validate_embedding_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"torch", "onnx", "openvino"}
        if normalized not in allowed:
            msg = "embedding_backend must be one of: torch, onnx, openvino"
            raise ValueError(msg)
        return normalized

    @field_validator("llm_model")
    @classmethod
    def _validate_llm_model(cls, value: str) -> str:
        return _validate_model_identifier(value, "llm_model")

    @field_validator("graph_query_level")
    @classmethod
    def _validate_graph_query_level(cls, value: GraphQueryLevel | str) -> GraphQueryLevel:
        if isinstance(value, str):
            value = value.strip().lower()
            if value not in ["simple", "medium", "advanced"]:
                msg = "graph_query_level must be one of: simple, medium, advanced"
                raise ValueError(msg)
            return value  # type: ignore[return-value]
        return value


__all__ = ["AiConfig", "Backend", "GraphQueryLevel"]
