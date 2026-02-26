"""Tests for AI configuration model and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdoc_crawler.ai.config import AiConfig
from tdoc_crawler.config import CacheManager


def test_from_env_reads_supported_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """AiConfig.from_env reads TDC_AI_* variables."""
    monkeypatch.setenv("TDC_AI_LLM_MODEL", "ollama/llama3.2")
    monkeypatch.setenv("TDC_AI_EMBEDDING_MODEL", "huggingface/BAAI/bge-small-en-v1.5")
    monkeypatch.setenv("TDC_AI_MAX_CHUNK_SIZE", "1200")
    monkeypatch.setenv("TDC_AI_CHUNK_OVERLAP", "120")
    monkeypatch.setenv("TDC_AI_PARALLELISM", "6")

    CacheManager(name="default").register(force=True)
    config = AiConfig.from_env(cache_manager_name="default")

    assert config.llm_model == "ollama/llama3.2"
    assert config.embedding_model == "huggingface/BAAI/bge-small-en-v1.5"
    assert config.max_chunk_size == 1200
    assert config.chunk_overlap == 120
    assert config.parallelism == 6


def test_model_identifier_requires_provider_prefix() -> None:
    """Model identifiers must follow <provider>/<model_name>."""
    with pytest.raises(ValueError, match="<provider>/<model_name>"):
        AiConfig(llm_model="llama3.2")

    with pytest.raises(ValueError, match="<provider>/<model_name>"):
        AiConfig(embedding_model="bge-small-en-v1.5")


def test_model_identifier_allows_nested_model_paths() -> None:
    """Model name segment may contain additional slashes."""
    config = AiConfig(
        llm_model="openai/gpt-4o-mini",
        embedding_model="huggingface/BAAI/bge-small-en-v1.5",
    )

    assert config.llm_model == "openai/gpt-4o-mini"
    assert config.embedding_model == "huggingface/BAAI/bge-small-en-v1.5"


def test_invalid_provider_is_rejected() -> None:
    """Unknown provider segment is rejected."""
    with pytest.raises(ValueError, match="provider"):
        AiConfig(llm_model="not-a-provider/gpt-x")


def test_default_store_path_resolves_under_cache_dir(tmp_path: Path) -> None:
    """Default AI store path resolves to <cache_dir>/.ai/lancedb."""
    CacheManager(root_path=tmp_path, name="test-ai-config").register(force=True)
    config = AiConfig(cache_manager_name="test-ai-config")

    assert str(config.ai_store_path).endswith(".ai\\lancedb") or str(config.ai_store_path).endswith(".ai/lancedb")
