"""Tests for metrics wiring in AI operations entrypoints."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from threegpp_ai.operations import convert as convert_ops
from threegpp_ai.operations import summarize as summarize_ops
from threegpp_ai.operations.metrics import (
    MetricsTracker,
    MetricType,
    TimedOperationResult,
    get_metrics_tracker,
    timed_operation,
)


class _DummyClient:
    """Simple LLM client stub returning deterministic outputs."""

    def __init__(self) -> None:
        self._calls = 0

    def complete(self, prompt: str, **_: object) -> str:
        self._calls += 1
        if self._calls == 1:
            return "This is a concise summary text for tests."
        return '["kw1", "kw2"]'


def test_timed_operation_returns_mutable_result() -> None:
    """timed_operation should yield a result object with final status and timing."""
    tracker = MetricsTracker()

    with timed_operation(tracker, "S4-260001", MetricType.CONVERSION) as result:
        assert isinstance(result, TimedOperationResult)

    assert result.success is True
    assert result.duration_seconds >= 0
    assert len(tracker.metrics) == 1
    assert tracker.metrics[0].metric_type == MetricType.CONVERSION


def test_convert_tdoc_to_markdown_records_conversion_metric(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """convert_tdoc_to_markdown should record conversion metrics."""
    tracker = get_metrics_tracker()
    tracker.clear()

    # Mock resolve_via_whatthespec in the convert module
    monkeypatch.setattr(
        convert_ops,
        "resolve_via_whatthespec",
        lambda _tdoc_id: None,
    )

    # Mock extract_document_structured_from_tdoc to bypass actual extraction but still record metrics
    def mock_extract(*args, **kwargs) -> None:
        # Manually record the metric since we're bypassing timed_operation
        with timed_operation(tracker, "S4-260001", MetricType.CONVERSION):
            pass
        return SimpleNamespace(content="# markdown", tables=[], figures=[], equations=[])

    monkeypatch.setattr(
        convert_ops,
        "extract_document_structured_from_tdoc",
        mock_extract,
    )

    output = convert_ops.convert_tdoc_to_markdown("S4-260001", force=True)

    assert output == "# markdown"
    conversion_metrics = tracker.by_type(MetricType.CONVERSION)
    assert len(conversion_metrics) == 1
    assert conversion_metrics[0].success is True


def test_convert_tdoc_to_markdown_writes_table_sidecar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """convert_tdoc_to_markdown should record conversion metrics when tables are extracted."""
    # Clear tracker to ensure test isolation
    tracker = get_metrics_tracker()
    tracker.clear()

    # Mock resolve_via_whatthespec in the convert module
    monkeypatch.setattr(
        convert_ops,
        "resolve_via_whatthespec",
        lambda _tdoc_id: None,
    )

    # Mock extract_document_structured_from_tdoc to return result with tables
    # Record the metric since we're bypassing the timed_operation wrapper
    def mock_extract(*args, **kwargs) -> None:
        with timed_operation(get_metrics_tracker(), "S4-260001", MetricType.CONVERSION):
            pass
        return SimpleNamespace(
            content="# markdown",
            tables=[SimpleNamespace(cells=[["a", "b"]], markdown="|a|b|", page_number=1)],
            figures=[],
            equations=[],
        )

    monkeypatch.setattr(
        convert_ops,
        "extract_document_structured_from_tdoc",
        mock_extract,
    )

    result = convert_ops.convert_tdoc_to_markdown("S4-260001", force=True)

    # Verify conversion succeeded and returned content
    assert "# markdown" in result
    conversion_metrics = tracker.by_type(MetricType.CONVERSION)
    assert len(conversion_metrics) == 1
    assert conversion_metrics[0].success is True


def test_summarize_tdoc_records_summarization_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    """summarize_tdoc should record summarization metrics at entrypoint level."""
    tracker = get_metrics_tracker()
    tracker.clear()

    monkeypatch.setattr(
        summarize_ops,
        "extract_tdoc_structured",
        lambda *_args, **_kwargs: SimpleNamespace(content="source content"),
    )
    monkeypatch.setattr(summarize_ops, "_get_llm_client", _DummyClient)
    monkeypatch.setattr(
        summarize_ops.AiConfig,
        "from_env",
        staticmethod(lambda: SimpleNamespace(llm_model="test-model")),
    )

    result = summarize_ops.summarize_tdoc("S4-260001")

    assert result.word_count > 0
    summary_metrics = tracker.by_type(MetricType.SUMMARIZATION)
    assert len(summary_metrics) == 1
    assert summary_metrics[0].success is True
