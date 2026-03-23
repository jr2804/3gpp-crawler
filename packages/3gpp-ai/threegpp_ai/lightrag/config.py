"""Configuration for LightRAG integration.

This module defines configuration dataclasses for LightRAG with:
- Storage backend selection (file-based, pg0, etc.)
- LLM and embedding model settings
- Query mode options

All constants are defined at module level in CAPS.
All choice/option types use StrEnum.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Constants (defaults and allowed values)
# =============================================================================

# LLM defaults
DEFAULT_LLM_MODEL: str = "qwen3:8b"
DEFAULT_LLM_HOST: str = "http://localhost:11434"
DEFAULT_LLM_PROVIDER: str = "ollama"

# Embedding defaults
DEFAULT_EMBEDDING_MODEL: str = "qwen3-embedding:0.6b"
DEFAULT_EMBEDDING_HOST: str = "http://localhost:11434"

# Storage defaults
DEFAULT_WORKING_DIR: str = "~/.3gpp-crawler/lightrag"
DEFAULT_WORKSPACE: str = "default"

# pg0 defaults
DEFAULT_PG0_INSTANCE_NAME: str = "3gpp-crawler"
DEFAULT_PG0_PORT: int = 15432
DEFAULT_PG0_DATABASE: str = "tdoc"


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
    """LLM configuration for LightRAG."""

    provider: str = Field(
        default=DEFAULT_LLM_PROVIDER,
        description="LLM provider (ollama, openai, etc.)",
    )
    model: str = Field(
        default=DEFAULT_LLM_MODEL,
        description="LLM model name",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for cloud LLM providers",
    )
    host: str = Field(
        default=DEFAULT_LLM_HOST,
        description="LLM API host URL",
    )

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_LLM_")


class EmbeddingConfig(BaseSettings):
    """Embedding model configuration for LightRAG."""

    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="Embedding model name",
    )
    host: str = Field(
        default=DEFAULT_EMBEDDING_HOST,
        description="Embedding API host URL",
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

    @property
    def pg_uri(self) -> str:
        """Return PostgreSQL connection URI for pg0."""
        return f"postgresql://postgres:postgres@localhost:{self.pg0_port}/{self.pg0_database}"

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_DB_")


# =============================================================================
# Main configuration
# =============================================================================


class LightRAGConfig(BaseSettings):
    """Main configuration for LightRAG integration.

    Uses file-based storage (NanoVectorDB, JsonKVStorage, NetworkX) by default.
    Set LIGHTRAG_DB_BACKEND=pg0 to use PostgreSQL via pg0.
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

    working_dir: str = Field(
        default=DEFAULT_WORKING_DIR,
        description="LightRAG working directory",
    )
    workspace: str = Field(
        default=DEFAULT_WORKSPACE,
        description="Default workspace name",
    )
    default_query_mode: QueryMode = Field(
        default=QueryMode.HYBRID,
        description="Default query mode",
    )

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG_")
