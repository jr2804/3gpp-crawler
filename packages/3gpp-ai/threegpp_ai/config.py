"""AI processing pipeline configuration for 3GPP documents.

This module extends the base ThreeGPPConfig with AI-specific settings
organized under the [ai] section in TOML/YAML/JSON configuration files.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from tdoc_crawler.config.env_vars import ConfigEnvVar
from tdoc_crawler.config.settings import ThreeGPPConfig

DEFAULT_LLM_MODEL = "openrouter/openrouter/free"

# Type aliases
ExtractionProfile = Literal["default", "balanced", "optimum", "custom"]
GraphQueryLevel = Literal["simple", "medium", "advanced"]


class AiConfig(BaseSettings):
    """AI processing pipeline configuration.

    Lives in 3gpp-ai package. Only primitive fields + format validators.
    No litellm import — provider validation is a separate concern.
    """

    model_config = SettingsConfigDict(extra="ignore")

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

    # Extraction profile policy
    extraction_profile: ExtractionProfile | None = Field(
        None,
        validation_alias=AliasChoices("TDC_AI_EXTRACTION_PROFILE", "extraction_profile"),
        description="Extraction profile override (default|balanced|optimum|custom). None enables deterministic auto-selection.",
    )
    custom_extract_ocr: bool = Field(
        True,
        validation_alias=AliasChoices("TDC_AI_CUSTOM_EXTRACT_OCR", "custom_extract_ocr"),
        description="Custom profile toggle: enable OCR stage",
    )
    custom_extract_layout: bool = Field(
        True,
        validation_alias=AliasChoices("TDC_AI_CUSTOM_EXTRACT_LAYOUT", "custom_extract_layout"),
        description="Custom profile toggle: enable layout stage",
    )
    custom_extract_tables: bool = Field(
        True,
        validation_alias=AliasChoices("TDC_AI_CUSTOM_EXTRACT_TABLES", "custom_extract_tables"),
        description="Custom profile toggle: enable table extraction",
    )
    custom_extract_figures: bool = Field(
        True,
        validation_alias=AliasChoices("TDC_AI_CUSTOM_EXTRACT_FIGURES", "custom_extract_figures"),
        description="Custom profile toggle: enable figure extraction",
    )
    custom_extract_equations: bool = Field(
        True,
        validation_alias=AliasChoices("TDC_AI_CUSTOM_EXTRACT_EQUATIONS", "custom_extract_equations"),
        description="Custom profile toggle: enable equation extraction",
    )
    custom_extract_enrichment: bool = Field(
        True,
        validation_alias=AliasChoices("TDC_AI_CUSTOM_EXTRACT_ENRICHMENT", "custom_extract_enrichment"),
        description="Custom profile toggle: enable enrichment stages",
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

    # Extraction toggles
    extract_tables: bool = Field(
        True,
        description="Enable extraction of table elements",
    )
    extract_figures: bool = Field(
        True,
        description="Enable extraction of figure elements",
    )
    extract_equations: bool = Field(
        True,
        description="Enable extraction of equation elements",
    )
    figure_description_enabled: bool = Field(
        True,
        description="Enable figure description generation with vision-capable models",
    )

    # Graph
    graph_query_level: GraphQueryLevel = Field(
        "simple",
        validation_alias=AliasChoices(ConfigEnvVar.TDC_GRAPH_QUERY_LEVEL.name, "graph_query_level"),
        description="Level of graph query answer generation (simple|medium|advanced)",
    )

    @model_validator(mode="after")
    def _validate_bounds(self) -> AiConfig:
        if self.abstract_max_words < self.abstract_min_words:
            msg = "abstract_max_words must be >= abstract_min_words"
            raise ValueError(msg)
        if self.chunk_overlap >= self.max_chunk_size:
            msg = "chunk_overlap must be less than max_chunk_size"
            raise ValueError(msg)
        return self

class ThreeGPPAIConfig(ThreeGPPConfig):
    """Extended config for 3gpp-ai, adding [ai] section.

    Inherits from_settings() from ThreeGPPConfig — loads all base
    sections (path, http, credentials, crawl) plus [ai].
    """

    ai: AiConfig = Field(default_factory=AiConfig)


__all__ = ["AiConfig", "ExtractionProfile", "GraphQueryLevel", "ThreeGPPAIConfig"]
