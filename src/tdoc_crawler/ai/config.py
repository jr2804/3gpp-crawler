"""Configuration for the AI document processing pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, model_validator

from tdoc_crawler.models.base import BaseConfigModel


def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


class AiConfig(BaseConfigModel):
    """Configuration for the AI processing pipeline."""

    ai_store_path: Path | None = Field(None, description="Path to AI LanceDB store")
    embedding_model: str = Field("BAAI/bge-small-en-v1.5", description="Embedding model name")
    max_chunk_size: int = Field(1000, ge=1, description="Max tokens per chunk")
    chunk_overlap: int = Field(100, ge=0, description="Token overlap between chunks")
    llm_model: str = Field("ollama/llama3.2", description="LLM model identifier")
    llm_api_base: str | None = Field(None, description="Override LLM API base URL")
    abstract_min_words: int = Field(150, ge=1, description="Minimum abstract word count")
    abstract_max_words: int = Field(250, ge=1, description="Maximum abstract word count")
    parallelism: int = Field(4, ge=1, le=32, description="Concurrent TDoc processing")

    @classmethod
    def from_env(cls, **overrides: object) -> AiConfig:
        """Create config from environment variables.

        Args:
            **overrides: Explicit values that take precedence over env vars.

        Returns:
            AiConfig instance populated from environment variables.
        """
        data: dict[str, object] = {}

        if store_path := os.getenv("TDC_AI_STORE_PATH"):
            data["ai_store_path"] = Path(store_path)
        if embedding_model := os.getenv("TDC_AI_EMBEDDING_MODEL"):
            data["embedding_model"] = embedding_model
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

        data.update(overrides)
        return cls(**data)

    @model_validator(mode="after")
    def _resolve_paths(self) -> AiConfig:
        if self.ai_store_path is None:
            self.ai_store_path = self.cache_dir / ".ai" / "lancedb"
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


__all__ = ["AiConfig"]
