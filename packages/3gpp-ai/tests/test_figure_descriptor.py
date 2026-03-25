"""Unit tests for figure description helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from threegpp_ai.operations import figure_descriptor


def test_describe_figures_disabled_returns_empty(tmp_path: Path) -> None:
    """Description generation should no-op when disabled."""
    image = tmp_path / "figure_1.png"
    image.write_bytes(b"png")

    result = figure_descriptor.describe_figures({"figure_1": image}, enabled=False)
    assert result == {}


def test_describe_figures_handles_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Description failures should be handled gracefully per figure."""
    image = tmp_path / "figure_1.png"
    image.write_bytes(b"png")

    monkeypatch.setattr(figure_descriptor, "_describe_figure", lambda *_args, **_kwargs: None)

    result = figure_descriptor.describe_figures({"figure_1": image}, enabled=True)
    assert result == {}


def test_describe_figures_returns_generated_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Description map should include successfully described figures."""
    image = tmp_path / "figure_1.png"
    image.write_bytes(b"png")

    monkeypatch.setattr(
        figure_descriptor,
        "_describe_figure",
        lambda *_args, **_kwargs: "A protocol stack diagram with control/data paths.",
    )

    result = figure_descriptor.describe_figures({"figure_1": image}, enabled=True)
    assert result["figure_1"].startswith("A protocol stack diagram")
