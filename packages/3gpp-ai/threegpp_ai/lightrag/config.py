"""Configuration for LightRAG integration.

This module defines configuration dataclasses for LightRAG with:
- Storage backend selection (file-based, pg0, etc.)
- LLM and embedding model settings with TDC_AI_* environment variable support
- Query mode options

All constants are defined at module level in CAPS.
All choice/option types use StrEnum.
"""

from __future__ import annotations

import os
from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Constants (defaults and allowed values)
# =============================================================================

# LLM defaults (read from TDC_AI_LLM_MODEL or use default)
DEFAULT_LLM_MODEL: str = os.getenv("TDC_AI_LLM_MODEL", "openrouter/openrouter/free")
DEFAULT_LLM_API_BASE: str = os.getenv("TDC_AI_LLM_API_BASE", "http://localhost:11434")

# Embedding defaults (read from TDC_AI_EMBEDDING_MODEL or use default)
DEFAULT_EMBEDDING_MODEL: str = os.getenv("TDC_AI_EMBEDDING_MODEL", "ollama/qwen3-embedding:0.6b")
DEFAULT_EMBEDDING_API_BASE: str = os.getenv("TDC_AI_EMBEDDING_API_BASE", "http://localhost:11434")

# Workspace default
DEFAULT_WORKSPACE: str = "default"

# pg0 defaults
DEFAULT_PG0_INSTANCE_NAME: str = "3gpp-crawler"
DEFAULT_PG0_PORT: int = 15432
DEFAULT_PG0_DATABASE: str = "tdoc"


# =============================================================================
# Helpers
# =============================================================================


def _env_bool(key: str, default: bool = True) -> bool:
    """Parse a boolean environment variable.

    Returns True for: "1", "true", "yes", "on"
    Returns False for: "0", "false", "no", "off"
    Returns default if the variable is not set.
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


# =============================================================================
# Enums
# =============================================================================


class StorageBackend(StrEnum):
    """Supported storage backends for LightRAG."""

    FILE = "file"
    PG0 = "pg0"


class QueryMode(StrEnum):
    """Supported query modes for LightRAG queries."""

    NAIVE = "naive"
    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"
    MIX = "mix"
    BYPASS = "bypass"


# =============================================================================
# Sub-configurations
# =============================================================================


class LLMConfig(BaseSettings):
    """LLM configuration for LightRAG.

    Supports <provider>/<model> syntax via TDC_AI_LLM_MODEL environment variable.
    Examples: openrouter/openrouter/free, ollama/qwen3:8b, anthropic/claude-3-sonnet
    """

    model: str = Field(
        default=DEFAULT_LLM_MODEL,
        description="LLM model name in <provider>/<model> format",
    )
    api_base: str = Field(
        default=DEFAULT_LLM_API_BASE,
        description="LLM API base URL",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for cloud LLM providers (overrides TDC_AI_LLM_API_KEY)",
    )

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_LLM_")


class EmbeddingConfig(BaseSettings):
    """Embedding model configuration for LightRAG.

    Supports <provider>/<model> syntax via TDC_AI_EMBEDDING_MODEL environment variable.
    Examples: sentence-transformers/all-MiniLM-L6-v2, ollama/qwen3-embedding:0.6b
    """

    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="Embedding model name in <provider>/<model> format",
    )
    api_base: str = Field(
        default=DEFAULT_EMBEDDING_API_BASE,
        description="Embedding API base URL",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for cloud embedding providers (overrides TDC_AI_EMBEDDING_API_KEY)",
    )

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_EMBEDDING_")


class DatabaseConfig(BaseSettings):
    """Database/storage backend configuration for LightRAG.

    Currently supports:
    - FILE: File-based storage (NanoVectorDB, JsonKVStorage, NetworkX)
    - PG0: PostgreSQL via pg0 (requires pg0 to be fixed on Windows)

    LightRAG storage types:
    - KV storage: JsonKVStorage (file) / PGKVStorage (pg0)
    - Vector storage: NanoVectorDBStorage (file) / PGVectorStorage (pg0)
    - DocStatus storage: JsonDocStatusStorage (file) / PGDocStatusStorage (pg0)
    - Graph storage: NetworkXStorage (file) / PGGraphStorage (pg0, requires AGE)
    """

    backend: StorageBackend = Field(
        default=StorageBackend.FILE,
        description="Storage backend to use",
    )
    pg0_instance_name: str = Field(
        default=DEFAULT_PG0_INSTANCE_NAME,
        description="pg0 instance name",
    )
    pg0_port: int = Field(
        default=DEFAULT_PG0_PORT,
        description="pg0 PostgreSQL port",
    )
    pg0_database: str = Field(
        default=DEFAULT_PG0_DATABASE,
        description="pg0 database name",
    )

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_DB_")


# =============================================================================
# Main configuration
# =============================================================================


class LightRAGConfig(BaseSettings):
    """Main configuration for LightRAG integration.

    Uses file-based storage (NanoVectorDB, JsonKVStorage, NetworkX) by default.
    Set LIGHTRAG_DB_BACKEND=pg0 to use PostgreSQL via pg0.
    Set LIGHTRAG_SHARED_STORAGE=true to enable cross-workspace embedding deduplication.

    Reads from TDC_AI_* environment variables for compatibility with legacy AiConfig:
    - TDC_AI_LLM_MODEL: LLM model in <provider>/<model> format
    - TDC_AI_LLM_API_BASE: LLM API base URL
    - TDC_AI_LLM_API_KEY: LLM API key
    - TDC_AI_EMBEDDING_MODEL: Embedding model in <provider>/<model> format
    """

    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM configuration",
    )
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="Embedding model configuration",
    )
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Storage backend configuration",
    )

    workspace: str = Field(
        default=DEFAULT_WORKSPACE,
        description="Default workspace name",
    )
    default_query_mode: QueryMode = Field(
        default=QueryMode.HYBRID,
        description="Default query mode",
    )
    shared_storage: bool = Field(
        default=False,
        description="Enable shared embedding storage across workspaces (deduplication). "
        "Note: Requires custom LightRAG integration - disable if using standard LightRAG.",
    )
    extract_tables: bool = Field(
        default=True,
        description="Enable extraction and indexing of table elements.",
    )
    extract_figures: bool = Field(
        default=True,
        description="Enable extraction and indexing of figure/image elements.",
    )
    extract_equations: bool = Field(
        default=True,
        description="Enable extraction and indexing of equation elements.",
    )
    figure_description_enabled: bool = Field(
        default=True,
        description="Enable optional figure description generation when vision-capable models are available.",
    )

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_")

    @classmethod
    def from_env(cls, **overrides) -> LightRAGConfig:
        """Create LightRAGConfig from TDC_AI_* environment variables.

        This method reads the legacy TDC_AI_* environment variables and maps them
        to LightRAG configuration, ensuring compatibility with the existing .env.example.

        Args:
            **overrides: Additional overrides that take precedence over env vars

        Returns:
            LightRAGConfig instance configured from environment
        """
        config_data: dict = {}

        # LLM config - pass through any set values, filter None
        llm_config = {
            "model": os.getenv("TDC_AI_LLM_MODEL"),
            "api_base": os.getenv("TDC_AI_LLM_API_BASE"),
            "api_key": os.getenv("TDC_AI_LLM_API_KEY"),
        }
        llm_config = {k: v for k, v in llm_config.items() if v is not None}
        if llm_config:
            config_data["llm"] = llm_config

        # Embedding config - pass through any set values, filter None
        embedding_config = {
            "model": os.getenv("TDC_AI_EMBEDDING_MODEL"),
            "api_base": os.getenv("TDC_AI_EMBEDDING_API_BASE"),
            "api_key": os.getenv("TDC_AI_EMBEDDING_API_KEY"),
        }
        embedding_config = {k: v for k, v in embedding_config.items() if v is not None}
        if embedding_config:
            config_data["embedding"] = embedding_config

        # Extraction toggles default to True
        config_data["extract_tables"] = _env_bool("LIGHTRAG_EXTRACT_TABLES", True)
        config_data["extract_figures"] = _env_bool("LIGHTRAG_EXTRACT_FIGURES", True)
        config_data["extract_equations"] = _env_bool("LIGHTRAG_EXTRACT_EQUATIONS", True)
        config_data["figure_description_enabled"] = _env_bool("LIGHTRAG_FIGURE_DESCRIPTION_ENABLED", True)

        config_data.update(overrides)
        return cls(**config_data)
