"""Unit tests for LightRAG configuration."""

import os

from threegpp_ai.lightrag.config import (
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
        assert config.model == "openrouter/openrouter/free"
        assert config.api_base == "http://localhost:11434"
        assert config.api_key is None

    def test_llm_config_custom(self) -> None:
        """Test LLM config with custom values."""
        config = LLMConfig(
            model="openai/gpt-4o-mini",
            api_base="https://api.openai.com",
            api_key="sk-test123",
        )
        assert config.model == "openai/gpt-4o-mini"
        assert config.api_base == "https://api.openai.com"
        assert config.api_key == "sk-test123"


class TestEmbeddingConfig:
    """Test EmbeddingConfig."""

    def test_embedding_config_defaults(self) -> None:
        """Test embedding config default values."""
        config = EmbeddingConfig()
        assert config.model == "ollama/qwen3-embedding:0.6b"
        assert config.api_base == "http://localhost:11434"
        assert config.api_key is None

    def test_embedding_config_custom(self) -> None:
        """Test embedding config with custom values."""
        config = EmbeddingConfig(
            model="openai/text-embedding-3-small",
            api_base="https://api.openai.com",
            api_key="sk-test123",
        )
        assert config.model == "openai/text-embedding-3-small"
        assert config.api_base == "https://api.openai.com"
        assert config.api_key == "sk-test123"


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
        assert config.llm.model == "openrouter/openrouter/free"
        assert config.embedding.model == "ollama/qwen3-embedding:0.6b"
        assert config.database.backend == StorageBackend.FILE
        assert config.default_query_mode == QueryMode.HYBRID

    def test_lightrag_config_with_subconfigs(self) -> None:
        """Test LightRAG config with sub-configs."""
        llm = LLMConfig(model="openai/gpt-4o")
        embedding = EmbeddingConfig(model="openai/text-embedding-3-small")
        database = DatabaseConfig(backend=StorageBackend.PG0)

        config = LightRAGConfig(
            llm=llm,
            embedding=embedding,
            database=database,
        )
        assert config.llm.model == "openai/gpt-4o"
        assert config.embedding.model == "openai/text-embedding-3-small"
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

    def test_lightrag_config_from_env(self) -> None:
        """Test LightRAGConfig.from_env() with TDC_AI_* variables."""
        os.environ["TDC_AI_LLM_MODEL"] = "openai/gpt-4o"
        os.environ["TDC_AI_EMBEDDING_MODEL"] = "openai/text-embedding-3-small"
        try:
            config = LightRAGConfig.from_env()
            assert config.llm.model == "openai/gpt-4o"
            assert config.embedding.model == "openai/text-embedding-3-small"
        finally:
            del os.environ["TDC_AI_LLM_MODEL"]
            del os.environ["TDC_AI_EMBEDDING_MODEL"]
