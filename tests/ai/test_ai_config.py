"""Tests for AI configuration model and validation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from threegpp_ai.config import AiConfig
from threegpp_ai.models import DocumentSummary

from tdoc_crawler.config import CacheManager


def test_from_env_reads_supported_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """AiConfig.from_env reads TDC_AI_* variables."""
    monkeypatch.setenv("TDC_AI_LLM_MODEL", "ollama/llama3.2")
    monkeypatch.setenv("TDC_AI_EMBEDDING_MODEL", "huggingface/BAAI/bge-small-en-v1.5")
    monkeypatch.setenv("TDC_AI_EMBEDDING_BACKEND", "openvino")
    monkeypatch.setenv("TDC_AI_MAX_CHUNK_SIZE", "1200")
    monkeypatch.setenv("TDC_AI_CHUNK_OVERLAP", "120")
    monkeypatch.setenv("TDC_AI_PARALLELISM", "6")

    CacheManager(name="default").register(force=True)
    config = AiConfig.from_env(cache_manager_name="default")

    assert config.llm_model == "ollama/llama3.2"
    assert config.embedding_model == "huggingface/BAAI/bge-small-en-v1.5"
    assert config.embedding_backend == "openvino"
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


def test_embedding_backend_defaults_to_torch() -> None:
    """Embedding backend defaults to torch when unset."""
    config = AiConfig(llm_model="openai/gpt-4o-mini")
    assert config.embedding_backend == "torch"


def test_embedding_backend_rejects_invalid_values() -> None:
    """Invalid embedding backend values are rejected."""
    with pytest.raises(ValueError, match="embedding_backend"):
        AiConfig(embedding_backend="cuda", llm_model="openai/gpt-4o-mini")


def test_default_store_path_resolves_under_cache_dir(tmp_path: Path) -> None:
    """Default AI store path resolves to <cache_dir>/.ai/<embedding_model>."""
    CacheManager(root_path=tmp_path, name="test-ai-config").register(force=True)
    config = AiConfig(cache_manager_name="test-ai-config")

    # Path should be under .ai directory with embedding model subdirectory
    assert ".ai" in str(config.ai_cache_dir)
    assert "sentence-transformers" in str(config.ai_cache_dir) or "all-MiniLM-L6-v2" in str(config.ai_cache_dir)


def test_no_hardcoded_models_in_ai_package() -> None:
    """T001 [US3]: Scan ai/ package for hardcoded model identifiers.

    Assert zero matches for model patterns (gpt-4o, llama3, ollama/llama, gpt-4o-mini)
    outside of config.py where defaults are defined.
    """
    ai_package = Path(__file__).resolve().parents[2] / "src" / "tdoc_crawler" / "ai"
    hardcoded_patterns = re.compile(r'["\']((?:gpt-4o[^"\']|llama3[^"\']|ollama/llama[^"\']|gpt-4o-mini))["\']', re.IGNORECASE)
    config_file = ai_package / "config.py"

    violations = []
    for py_file in ai_package.rglob("*.py"):
        if py_file == config_file:
            continue  # Skip config.py where defaults are defined

        content = py_file.read_text(encoding="utf-8")
        matches = hardcoded_patterns.findall(content)
        if matches:
            violations.append(f"{py_file.relative_to(ai_package)}: {matches}")

    assert not violations, f"Found hardcoded model identifiers in: {'\n  '.join(violations)}"


def test_model_config_propagation_to_litellm_client() -> None:
    """T002 [US3]: Verify LiteLLMClient uses AiConfig().llm_model when no explicit model passed.

    This test verifies the bug fix where DocumentSummary.llm_model should use
    default_factory=lambda: AiConfig().llm_model instead of hardcoded default.
    """
    # Initialize cache manager (required by AiConfig)
    CacheManager(name="test-config-prop").register(force=True)

    # Get the config default
    config = AiConfig(cache_manager_name="test-config-prop")
    config_default = config.llm_model

    # Get the DocumentSummary default
    summary_default = DocumentSummary.model_fields["llm_model"].default_factory()

    # They should match
    assert summary_default == config_default, f"DocumentSummary.llm_model default ({summary_default}) does not match AiConfig().llm_model ({config_default})"
