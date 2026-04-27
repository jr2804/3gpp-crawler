"""Structured-context summarize behavior tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from threegpp_ai.operations import summarize as summarize_ops


class _CaptureClient:
    """Deterministic client that records prompts for assertions."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self._calls = 0

    def complete(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        self._calls += 1
        if self._calls == 1:
            return "Structured summary text"
        return '["kw1", "kw2"]'


def _base_config() -> SimpleNamespace:
    return SimpleNamespace(llm_model="test-model", quality_policy_mode="balanced", allow_failed_quality=False)


def test_serialize_structured_context_budget_and_determinism() -> None:
    extraction = SimpleNamespace(
        equations=[
            SimpleNamespace(element_id="equation_2", page_number=14, normalized_text="x + y = z", raw_text=None, latex="x+y=z"),
            SimpleNamespace(element_id="equation_1", page_number=12, normalized_text="a + b = c", raw_text=None, latex="a+b=c"),
        ],
        tables=[SimpleNamespace(element_id="table_1", page_number=11, row_count=3, column_count=4, caption="Procedure steps")],
        figures=[SimpleNamespace(element_id="figure_1", page_number=13, caption="Architecture", description=None)],
    )

    text_a, stats_a = summarize_ops._serialize_structured_context(extraction, max_chars=180)
    text_b, stats_b = summarize_ops._serialize_structured_context(extraction, max_chars=180)

    assert text_a == text_b
    assert stats_a == stats_b
    assert len(text_a) <= 180
    assert "Equation equation_1 (p. 12)" in text_a


def test_summarize_uses_structured_context_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    capture = _CaptureClient()
    extraction = SimpleNamespace(
        content="markdown body",
        metadata={"extraction_status": "ok"},
        equations=[SimpleNamespace(element_id="equation_7", page_number=14, normalized_text="a + b = c", raw_text=None, latex="a+b=c")],
        tables=[],
        figures=[],
    )

    monkeypatch.setattr(summarize_ops, "extract_document_structured_from_tdoc", lambda *_args, **_kwargs: extraction)
    monkeypatch.setattr(summarize_ops, "_get_llm_client", lambda: capture)
    monkeypatch.setattr(summarize_ops, "AiConfig", _base_config)

    result = summarize_ops.summarize_tdoc("S4-260001")

    assert result.metadata["context_mode"] == "structured"
    assert "Structured references" in capture.prompts[0]
    assert "Equation equation_7 (p. 14)" in capture.prompts[0]


def test_summarize_falls_back_to_markdown_when_structured_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    capture = _CaptureClient()
    extraction = SimpleNamespace(
        content="legacy markdown only content",
        metadata={"extraction_status": "ok"},
        equations=[],
        tables=[],
        figures=[],
    )

    monkeypatch.setattr(summarize_ops, "extract_document_structured_from_tdoc", lambda *_args, **_kwargs: extraction)
    monkeypatch.setattr(summarize_ops, "_get_llm_client", lambda: capture)
    monkeypatch.setattr(summarize_ops, "AiConfig", _base_config)

    result = summarize_ops.summarize_tdoc("S4-260001")

    assert result.metadata["context_mode"] == "markdown_fallback"
    assert "Structured references" not in capture.prompts[0]
    assert "legacy markdown only content" in capture.prompts[0]
