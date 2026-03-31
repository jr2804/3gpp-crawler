"""AI processing pipeline configuration for 3GPP documents.

This module extends the base ThreeGPPConfig with AI-specific settings
organized under the [ai] section in TOML/YAML/JSON configuration files.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from tdoc_crawler.config.env_vars import ConfigEnvVar
from tdoc_crawler.config.settings import ThreeGPPConfig

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LLM_MODEL = "openrouter/openrouter/free"

# Type aliases
Backend = Literal["torch", "onnx", "openvino"]
GraphQueryLevel = Literal["simple", "medium", "advanced"]
QueryMode = Literal["naive", "local", "global", "hybrid", "mix", "bypass"]
StorageBackend = Literal["file", "pg0"]


class LightRAGSettings(BaseSettings):
    """LightRAG-specific configuration (nested under ai.lightrag)."""

    model_config = SettingsConfigDict(extra="ignore")

    # Storage backend
    db_backend: StorageBackend = Field(
        "file",
        validation_alias=AliasChoices(ConfigEnvVar.LIGHTRAG_DB_BACKEND.name, "db_backend"),
        description="Storage backend to use (file or pg0)",
    )
    pg0_instance_name: str = Field(
        "3gpp-crawler",
        description="pg0 instance name",
    )
    pg0_port: int = Field(
        15432,
        ge=1,
        le=65535,
        description="pg0 PostgreSQL port",
    )
    pg0_database: str = Field(
        "tdoc",
        description="pg0 database name",
    )

    # Workspace / query
    workspace: str = Field(
        "default",
        description="Default workspace name",
    )
    default_query_mode: QueryMode = Field(
        "hybrid",
        description="Default query mode",
    )

    # Feature toggles
    shared_storage: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.LIGHTRAG_SHARED_STORAGE.name, "shared_storage"),
        description="Enable shared embedding storage across workspaces (deduplication)",
    )
    extract_tables: bool = Field(
        True,
        description="Enable extraction and indexing of table elements",
    )
    extract_figures: bool = Field(
        True,
        description="Enable extraction and indexing of figure elements",
    )
    extract_equations: bool = Field(
        True,
        description="Enable extraction and indexing of equation elements",
    )
    figure_description_enabled: bool = Field(
        True,
        description="Enable figure description generation with vision-capable models",
    )


class AiConfig(BaseSettings):
    """AI processing pipeline configuration.

    Lives in 3gpp-ai package. Only primitive fields + format validators.
    No litellm import — provider validation is a separate concern.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # Embedding
    embedding_model: str = Field(
        DEFAULT_EMBEDDING_MODEL,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_MODEL.name, "embedding_model"),
        description="Embedding model in <provider>/<model_name> format",
    )
    embedding_backend: Backend = Field(
        "torch",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_BACKEND.name, "embedding_backend"),
        description="Sentence-transformers backend (torch, onnx, openvino)",
    )
    embedding_api_base: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_API_BASE.name, "embedding_api_base"),
        description="Override Embedding API base URL",
    )
    embedding_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_EMBEDDING_API_KEY.name, "embedding_api_key"),
        description="Override Embedding API key",
    )

    # LLM
    llm_model: str = Field(
        DEFAULT_LLM_MODEL,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_LLM_MODEL.name, "llm_model"),
        description="LLM model in <provider>/<model_name> format",
    )
    llm_api_base: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_LLM_API_BASE.name, "llm_api_base"),
        description="Override LLM API base URL",
    )
    llm_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_LLM_API_KEY.name, "llm_api_key"),
        description="Override LLM API key (takes precedence over provider env vars)",
    )

    # Chunking
    max_chunk_size: int = Field(
        1000,
        ge=1,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_MAX_CHUNK_SIZE.name, "max_chunk_size"),
        description="Max tokens per chunk",
    )
    chunk_overlap: int = Field(
        100,
        ge=0,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_CHUNK_OVERLAP.name, "chunk_overlap"),
        description="Token overlap between chunks",
    )

    # Processing
    abstract_min_words: int = Field(
        150,
        ge=1,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_ABSTRACT_MIN_WORDS.name, "abstract_min_words"),
        description="Minimum abstract word count",
    )
    abstract_max_words: int = Field(
        250,
        ge=1,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_ABSTRACT_MAX_WORDS.name, "abstract_max_words"),
        description="Maximum abstract word count",
    )
    parallelism: int = Field(
        4,
        ge=1,
        le=32,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_PARALLELISM.name, "parallelism"),
        description="Concurrent TDoc processing",
    )
    convert_pdf: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_CONVERT_PDF.name, "convert_pdf"),
        description="Convert PDF documents to markdown",
    )
    convert_md: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_CONVERT_MD.name, "convert_md"),
        description="Enable markdown conversion for documents",
    )
    vlm: bool = Field(
        False,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_VLM.name, "vlm"),
        description="Use Vision-Language Models for figure analysis",
    )
    device: str = Field(
        "auto",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_DEVICE.name, "device"),
        description="Device to use for local models (auto|cpu|cuda|mps)",
    )
    num_threads: int | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_NUM_THREADS.name, "num_threads"),
        description="Number of threads for parallel processing",
    )
    batch_size: int | None = Field(
        None,
        validation_alias=AliasChoices(ConfigEnvVar.TDC_AI_BATCH_SIZE.name, "batch_size"),
        description="Batch size for processing",
    )

    # Graph
    graph_query_level: GraphQueryLevel = Field(
        "simple",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_GRAPH_QUERY_LEVEL.name, "graph_query_level"),
        description="Level of graph query answer generation (simple|medium|advanced)",
    )

    # LightRAG nested
    lightrag: LightRAGSettings = Field(default_factory=LightRAGSettings)

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
        if "/" not in value:
            msg = "embedding_model must be in '<provider>/<model_name>' format"
            raise ValueError(msg)
        return value

    @field_validator("llm_model")
    @classmethod
    def _validate_llm_model(cls, value: str) -> str:
        if "/" not in value:
            msg = "llm_model must be in '<provider>/<model_name>' format"
            raise ValueError(msg)
        return value


class ThreeGPPAIConfig(ThreeGPPConfig):
    """Extended config for 3gpp-ai, adding [ai] section.

    Inherits from_settings() from ThreeGPPConfig — loads all base
    sections (path, http, credentials, crawl) plus [ai].
    """

    ai: AiConfig = Field(default_factory=AiConfig)


__all__ = ["AiConfig", "Backend", "GraphQueryLevel", "LightRAGSettings", "ThreeGPPAIConfig"]
