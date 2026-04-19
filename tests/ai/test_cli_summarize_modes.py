"""CLI summarize output mode tests."""

from __future__ import annotations

from types import SimpleNamespace

from threegpp_ai.cli import app
from typer.testing import CliRunner


def _stub_result(*_args: object, **_kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(
        summary="Summary body",
        keywords=["kw1", "kw2"],
        metadata={"extraction_status": "ok"},
    )


def test_summarize_default_standard_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("threegpp_ai.cli.summarize_document", _stub_result)

    result = runner.invoke(app, ["summarize", "S4-260001"])

    assert result.exit_code == 0
    assert "## Summary for S4-260001" in result.stdout
    assert "## Wiki Summary" not in result.stdout


def test_summarize_wiki_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("threegpp_ai.cli.summarize_document", _stub_result)

    result = runner.invoke(app, ["summarize", "S4-260001", "--output-mode", "wiki"])

    assert result.exit_code == 0
    assert "## Wiki Summary for S4-260001" in result.stdout
    assert "### Abstract" in result.stdout
    assert "### Keywords" in result.stdout
    assert "### Source Quality" in result.stdout


def test_summarize_rejects_invalid_output_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("threegpp_ai.cli.summarize_document", _stub_result)

    result = runner.invoke(app, ["summarize", "S4-260001", "--output-mode", "invalid"])

    assert result.exit_code != 0
    combined_output = f"{result.stdout}\n{result.stderr}\n{result.output}"
    assert "--output-mode" in combined_output
    assert "invalid" in combined_output.lower()
