"""Tests for load_dotenv consolidation in CLI entry point."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tdoc_crawler.config import TDocCrawlerConfig


class TestLoadDotenvConsolidation:
    """Test that load_dotenv is called once at CLI entry."""

    def test_no_duplicate_dotenv_calls(self) -> None:
        """Verify load_dotenv is not called in submodule CLI files."""
        cli_dir = Path(__file__).parent.parent / "src" / "tdoc_crawler" / "cli"
        submodule_files = [
            "crawl.py",
            "query.py",
            "specs.py",
        ]

        for filename in submodule_files:
            filepath = cli_dir / filename
            if filepath.exists():
                source = filepath.read_text()
                tree = ast.parse(source)

                # Check for load_dotenv import
                has_import = any(
                    isinstance(node, ast.ImportFrom) and node.module == "dotenv" and any(alias.name == "load_dotenv" for alias in node.names)
                    for node in ast.walk(tree)
                )

                # Check for load_dotenv() call
                has_call = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "load_dotenv" for node in ast.walk(tree))

                assert not has_import, f"{filename} should not import load_dotenv"
                assert not has_call, f"{filename} should not call load_dotenv()"

    def test_tdoc_app_has_load_dotenv(self) -> None:
        """tdoc_app.py should import and call load_dotenv."""
        app_file = Path(__file__).parent.parent / "src" / "tdoc_crawler" / "cli" / "tdoc_app.py"
        source = app_file.read_text()
        tree = ast.parse(source)

        # Check for load_dotenv import
        has_import = any(
            isinstance(node, ast.ImportFrom) and node.module == "dotenv" and any(alias.name == "load_dotenv" for alias in node.names) for node in ast.walk(tree)
        )

        # Check for load_dotenv() call
        has_call = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "load_dotenv" for node in ast.walk(tree))

        assert has_import, "tdoc_app.py should import load_dotenv"
        assert has_call, "tdoc_app.py should call load_dotenv()"


class TestBackwardCompatibility:
    """Test that existing .env patterns still work."""

    def test_existing_env_vars_still_work(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Direct environment variables still take precedence."""
        test_path = Path.home() / ".explicit_cache_test"
        monkeypatch.setenv("TDC_CACHE_DIR", str(test_path))

        config = TDocCrawlerConfig()

        assert config.path.cache_dir == test_path

    def test_http_cache_env_vars_work(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTP_CACHE_TTL env var still works."""
        monkeypatch.setenv("HTTP_CACHE_TTL", "3600")

        config = TDocCrawlerConfig()

        assert config.http.cache_ttl == 3600

    def test_dotenv_called_before_other_imports(self) -> None:
        """load_dotenv() is called at module level before other imports."""
        app_file = Path(__file__).parent.parent / "src" / "tdoc_crawler" / "cli" / "tdoc_app.py"
        source = app_file.read_text()

        # Find line numbers of key elements
        lines = source.split("\n")

        load_dotenv_line = -1
        typer_import_line = -1

        for i, line in enumerate(lines):
            if "load_dotenv()" in line and not line.strip().startswith("#"):
                load_dotenv_line = i
            if "import typer" in line and not line.strip().startswith("#"):
                typer_import_line = i

        assert load_dotenv_line > 0, "load_dotenv() call should exist"
        assert typer_import_line > 0, "import typer should exist"
        assert load_dotenv_line < typer_import_line, "load_dotenv() should be called before other imports"
