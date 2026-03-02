"""Tests for document summarization."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tdoc_crawler.ai.models import DocumentSummary, LlmConfigError
from tdoc_crawler.ai.operations import summarize
from tdoc_crawler.ai.operations.summarize import _count_words, _should_skip_summary
from tdoc_crawler.ai.storage import AiStorage


class TestSummarization:
    """Tests for summarization functions."""

    def test_abstract_word_count(self) -> None:
        """Test that abstract word count is 150-250 words."""
        # 150-250 words should pass
        text_200 = " ".join(["word"] * 200)
        assert 150 <= _count_words(text_200) <= 250

        # Too short should fail
        text_50 = " ".join(["word"] * 50)
        assert _count_words(text_50) < 150

    def test_structured_summary_has_required_fields(self) -> None:
        """Test structured summary has key_points, action_items, decisions, affected_specs."""
        # Create a summary with required fields
        summary = DocumentSummary(
            document_id="SP-123456",
            abstract="Test abstract",
            key_points=["Point 1", "Point 2"],
            action_items=["Action 1"],
            decisions=["Decision 1"],
            affected_specs=["TS 26.260"],
        )

        assert summary.key_points is not None
        assert summary.action_items is not None
        assert summary.decisions is not None
        assert summary.affected_specs is not None

    def test_skip_unchanged_tdoc(self) -> None:
        """Test that unchanged TDoc is skipped for summarization."""
        with patch("tdoc_crawler.ai.operations.summarize.storage") as mock:
            mock.get_summary_hash.return_value = "abc123"
            result = _should_skip_summary("SP-123456", "abc123")
            assert result is True

    def test_summarize_document_parses_structured_llm_output(self, tmp_path: Path) -> None:
        """Summarizer should parse structured JSON output from LLM."""
        ai_store = AiStorage(tmp_path / "lancedb")
        tdoc_id = "S4-260001"
        markdown = "# Title\n\nDiscussion on TS 26.260 and CR updates."
        abstract = " ".join(["word"] * 180)
        structured_json = json.dumps(
            {
                "key_points": ["Point A", "Point B"],
                "action_items": ["Action A"],
                "decisions": ["Decision A"],
                "affected_specs": ["TS 26.260"],
            }
        )

        with patch("tdoc_crawler.ai.operations.summarize._get_llm_client") as get_client:
            mock_client = get_client.return_value
            mock_client.complete.side_effect = [abstract, structured_json]

            summary = summarize.summarize_document(tdoc_id, markdown, storage=ai_store)

        assert isinstance(summary, DocumentSummary)
        assert summary.key_points == ["Point A", "Point B"]
        assert summary.action_items == ["Action A"]
        assert summary.decisions == ["Decision A"]
        assert summary.affected_specs == ["TS 26.260"]
        assert mock_client.complete.call_count == 2

    def test_missing_llm_model_config_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing/invalid LLM config should raise LlmConfigError."""
        monkeypatch.setattr(
            "tdoc_crawler.ai.operations.summarize.AiConfig.from_env",
            lambda **kwargs: (_ for _ in ()).throw(ValueError("llm_model missing")),
        )

        with pytest.raises(LlmConfigError):
            summarize.summarize_document("S4-260001", "# sample markdown")

    def test_unreachable_llm_endpoint_raises_error(self, tmp_path: Path) -> None:
        """Connection failures must surface as LlmConfigError."""
        ai_store = AiStorage(tmp_path / "lancedb")

        with patch("tdoc_crawler.ai.operations.summarize._get_llm_client") as get_client:
            mock_client = get_client.return_value
            mock_client.complete.side_effect = ConnectionError("endpoint unreachable")

            with pytest.raises(LlmConfigError):
                summarize.summarize_document("S4-260001", "# markdown", storage=ai_store)


class TestSummarizationModuleExports:
    """Tests that summarize module exports required functions."""

    def test_summarize_document_exported(self) -> None:
        """Verify summarize_document is exported."""
        assert hasattr(summarize, "summarize_document")
        assert callable(summarize.summarize_document)


US5_T050_RED_CHECKPOINT = """
Command: uv run pytest tests/ai/test_ai_summarization.py -q

Observed failure:
- TestSummarization.test_summarize_document_parses_structured_llm_output
    AssertionError: expected key_points parsed from structured JSON payload,
    got fallback sentence extraction from abstract.
- TestSummarization.test_missing_llm_model_config_raises_error
    ValueError raised from AiConfig loading instead of LlmConfigError.
- TestSummarization.test_unreachable_llm_endpoint_raises_error
    ConnectionError surfaced directly instead of LlmConfigError.

Checkpoint status: RED (3 failed, 4 passed)
"""
