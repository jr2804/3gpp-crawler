"""Unit tests for LightRAG configuration."""

import os

from tdoc_ai.lightrag.config import (
    DatabaseConfig,
    EmbeddingConfig,
    LightRAGConfig,
    LLMConfig,
    QueryMode,
    StorageBackend,
)


class TestStorageBackend:
    """Test StorageBackend enum."""

    def test_storage_backend_values(self) -> None:
        """Test storage backend enum values."""
        assert StorageBackend.FILE.value == "file"
        assert StorageBackend.PG0.value == "pg0"


class TestQueryMode:
    """Test QueryMode enum."""

    def test_query_mode_values(self) -> None:
        """Test query mode enum values."""
        assert QueryMode.NAIVE.value == "naive"
        assert QueryMode.LOCAL.value == "local"
        assert QueryMode.GLOBAL.value == "global"
        assert QueryMode.HYBRID.value == "hybrid"
        assert QueryMode.MIX.value == "mix"
        assert QueryMode.BYPASS.value == "bypass"


class TestLLMConfig:
    """Test LLMConfig."""

    def test_llm_config_defaults(self) -> None:
        """Test LLM config default values."""
        config = LLMConfig()
        assert config.provider == "ollama"
        assert config.model == "qwen3:8b"
        assert config.host == "http://localhost:11434"
        assert config.api_key is None

    def test_llm_config_custom(self) -> None:
        """Test LLM config with custom values."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-test123",
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.api_key == "sk-test123"


class TestEmbeddingConfig:
    """Test EmbeddingConfig."""

    def test_embedding_config_defaults(self) -> None:
        """Test embedding config default values."""
        config = EmbeddingConfig()
        assert config.model == "qwen3-embedding:0.6b"
        assert config.host == "http://localhost:11434"

    def test_embedding_config_custom(self) -> None:
        """Test embedding config with custom values."""
        config = EmbeddingConfig(
            model="text-embedding-3-small",
            host="https://api.openai.com",
        )
        assert config.model == "text-embedding-3-small"
        assert config.host == "https://api.openai.com"


class TestDatabaseConfig:
    """Test DatabaseConfig."""

    def test_database_config_defaults(self) -> None:
        """Test database config default values."""
        config = DatabaseConfig()
        assert config.backend == StorageBackend.FILE
        assert config.pg0_instance_name == "3gpp-crawler"
        assert config.pg0_port == 15432
        assert config.pg0_database == "tdoc"

    def test_database_config_pg_uri(self) -> None:
        """Test pg_uri property."""
        config = DatabaseConfig(
            backend=StorageBackend.PG0,
            pg0_port=15433,
            pg0_database="test",
        )
        assert config.pg_uri == "postgresql://postgres:postgres@localhost:15433/test"


class TestLightRAGConfig:
    """Test LightRAGConfig."""

    def test_lightrag_config_defaults(self) -> None:
        """Test LightRAG config default values."""
        config = LightRAGConfig()
        assert config.llm.provider == "ollama"
        assert config.llm.model == "qwen3:8b"
        assert config.embedding.model == "qwen3-embedding:0.6b"
        assert config.database.backend == StorageBackend.FILE
        assert config.working_dir.endswith(".3gpp-crawler/lightrag")
        assert config.default_query_mode == QueryMode.HYBRID

    def test_lightrag_config_with_subconfigs(self) -> None:
        """Test LightRAG config with sub-configs."""
        llm = LLMConfig(provider="openai", model="gpt-4o")
        embedding = EmbeddingConfig(model="text-embedding-3-small")
        database = DatabaseConfig(backend=StorageBackend.PG0)

        config = LightRAGConfig(
            llm=llm,
            embedding=embedding,
            database=database,
        )
        assert config.llm.provider == "openai"
        assert config.embedding.model == "text-embedding-3-small"
        assert config.database.backend == StorageBackend.PG0

    def test_lightrag_config_env_prefix(self) -> None:
        """Test environment variable prefix."""
        # LightRAGConfig uses env_prefix="LIGHTRAG_"
        os.environ["LIGHTRAG_WORKING_DIR"] = "/custom/path"
        try:
            config = LightRAGConfig()
            assert config.working_dir == "/custom/path"
        finally:
            del os.environ["LIGHTRAG_WORKING_DIR"]
