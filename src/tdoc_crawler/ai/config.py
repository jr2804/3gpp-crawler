"""Configuration for the AI document processing pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from tdoc_crawler.models import BaseConfigModel

DEFAULT_EMBEDDING_MODEL = "ollama/embeddinggemma"
DEFAULT_LLM_MODEL = "openrouter/openrouter/free"

LITELLM_PROVIDER_ALLOWLIST = {
    "openai",
    "anthropic",
    "azure",
    "google",
    "vertex_ai",
    "cohere",
    "huggingface",
    "ollama",
    "groq",
    "mistral",
    "bedrock",
    "replicate",
    "together_ai",
    # Cloud platforms and aggregators
    "openrouter",  # Multi-provider aggregator
    "github_copilot",  # GitHub Copilot (Azure-based)
    "nvidia",  # NVIDIA NIM
    "sambanova",  # SambaNova Cloud
    "fireworks_ai",  # Fireworks AI
    "anyscale",  # Anyscale Endpoints
    "perplexity",  # Perplexity API
    "deepinfra",  # DeepInfra
}


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
    if provider_normalized not in LITELLM_PROVIDER_ALLOWLIST:
        msg = f"{field_name} provider '{provider}' is not in supported provider allowlist: {sorted(LITELLM_PROVIDER_ALLOWLIST)}"
        raise ValueError(msg)

    return f"{provider_normalized}/{model_name_normalized}"


class AiConfig(BaseConfigModel):
    """Configuration for the AI processing pipeline."""

    ai_store_path: Path | None = Field(None, description="Path to AI LanceDB store")

    embedding_model: str = Field(
        DEFAULT_EMBEDDING_MODEL,
        description="Embedding model in <provider>/<model_name> format",
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

    @classmethod
    def from_env(cls, **overrides: str | int | Path | None) -> AiConfig:
        """Create config from environment variables."""
        data: dict[str, str | int | Path | None] = {}

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
        # Filter out None values to let defaults apply
        filtered_data = {k: v for k, v in data.items() if v is not None}
        return cls(**filtered_data)  # type: ignore[arg-type]

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

    @field_validator("embedding_model")
    @classmethod
    def _validate_embedding_model(cls, value: str) -> str:
        return _validate_model_identifier(value, "embedding_model")

    @field_validator("llm_model")
    @classmethod
    def _validate_llm_model(cls, value: str) -> str:
        return _validate_model_identifier(value, "llm_model")


__all__ = ["LITELLM_PROVIDER_ALLOWLIST", "AiConfig"]
