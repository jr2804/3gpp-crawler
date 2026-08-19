"""Regression test: Click's Windows glob expansion must not rewrite glob-pattern option values.

Issue #2: on Windows, Click's default `Command.main(windows_expand_args=True)`
rewrites any option value containing `*`/`?`/`[` against the CWD before it
reaches the callback. For data fields like `--title`/`--agenda` that carry
arbitrary glob patterns, this silently turns `*ATIAS*` into whatever filename
happens to live in the caller's directory.

`GlobSafeTyper` disables this expansion so the value reaches the query as the
user typed it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from tdoc_crawler.cli._shared import GlobSafeTyper


def test_glob_safe_typer_is_typer_subclass() -> None:
    assert issubclass(GlobSafeTyper, typer.Typer)


def test_cli_apps_use_glob_safe_typer() -> None:
    """Every CLI entry-point app must override Click's Windows glob expansion."""
    from tdoc_crawler.cli.config_app import config_app
    from tdoc_crawler.cli.mcp_app import app as mcp_app
    from tdoc_crawler.cli.mgmt_app import mgmt_app
    from tdoc_crawler.cli.spec_app import spec_app
    from tdoc_crawler.cli.tag_app import app as tag_app
    from tdoc_crawler.cli.tdoc_app import tdoc_app

    for app in (mgmt_app, tdoc_app, spec_app, tag_app, mcp_app, config_app):
        assert isinstance(app, GlobSafeTyper), f"{app!r} is not GlobSafeTyper"


def test_argv_glob_value_not_rewritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repro of issue #2: with a matching file present in CWD, the literal
    `*ATIAS*` passed via sys.argv reaches the callback unexpanded."""
    import tempfile

    # CWD contains a file whose name is what Windows glob of `*ATIAS*` would produce.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "debug_atias.py").write_text("pass")

    captured: dict[str, object] = {}
    app = GlobSafeTyper()

    @app.command()
    def _cmd(title: list[str] | None = None) -> None:
        captured["title"] = title

    # Drive via sys.argv, the exact path Click would glob-expand on Windows.
    monkeypatch.setattr(sys, "argv", ["app", "--title", "*ATIAS*"])
    # GlobSafeTyper.__call__ invokes `.main(windows_expand_args=False)`.
    app(standalone_mode=False)

    assert captured["title"] == ["*ATIAS*"]


def test_glob_expansion_would_occur_with_plain_typer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check: a plain Typer DOES glob-expand on Windows, proving the fix matters.

    Skipped on non-Windows where Click does not expand by default.
    """
    if os.name != "nt":
        pytest.skip("Windows-specific Click behavior")

    monkeypatch.chdir(tmp_path)
    (tmp_path / "debug_atias.py").write_text("pass")

    captured: dict[str, object] = {}
    app = typer.Typer()

    @app.command()
    def _cmd(title: list[str] | None = None) -> None:
        captured["title"] = title

    monkeypatch.setattr(sys, "argv", ["app", "--title", "*ATIAS*"])
    app(standalone_mode=False)

    # Plain Typer rewrites the glob against CWD.
    assert captured["title"] == ["debug_atias.py"]


def test_glob_safe_typer_passes_through_explicit_args() -> None:
    """Calling with explicit args (not sys.argv) still works as a normal Typer."""
    app = GlobSafeTyper()

    @app.command()
    def echo(theme: str | None = None) -> None:
        typer.echo(f"theme={theme}")

    runner = CliRunner()
    result = runner.invoke(app, ["--theme", "dark"])
    assert result.exit_code == 0
    assert "theme=dark" in result.output