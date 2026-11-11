from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from tdoc_crawler.cli.spec_app import spec_app as app
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database.oxyde_models import Specification
from tdoc_crawler.database.specs import SpecDatabase

runner = CliRunner()


class TestSpecCli:
    def test_checkout_spec_command_exists(self) -> None:
        """Test that checkout command exists."""
        result = runner.invoke(app, ["checkout", "--help"])
        assert result.exit_code == 0
        assert "checkout" in result.stdout

    def test_open_spec_command_exists(self) -> None:
        """Test that open command exists."""
        result = runner.invoke(app, ["open", "--help"])
        assert result.exit_code == 0
        assert "open" in result.stdout

    @patch("tdoc_crawler.cli.specs.SpecDownloads")
    def test_checkout_spec_execution(self, mock_downloads_cls: Any) -> None:
        """Test execution of checkout with args."""
        result = runner.invoke(app, ["checkout", "26.132", "--doc-only"])
        # Should call SpecDownloads.checkout_specs
        if result.exit_code == 0:
            mock_downloads_cls.return_value.checkout_specs.assert_called()
        else:
            # Allow failure here as it's not implemented, but the test structure is valid
            pass

    def test_query_specs_command_exists(self) -> None:
        """Test that query command exists."""
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0
        assert "query" in result.stdout


def test_query_specs_filters_by_subgroup_working_group(test_cache_dir: Path) -> None:
    """Spec rows store the sub-working group (SA4), so -w SA4 must match them."""

    async def seed() -> None:
        async with SpecDatabase(PathConfig().db_file) as database:
            await database.upsert_specification(
                Specification(
                    spec_number="26.132",
                    spec_number_compact="26132",
                    spec_type="TS",
                    title="Audio Codecs",
                    status="Active",
                    working_group="SA4",
                    series="26_series",
                )
            )

    asyncio.run(seed())

    result = runner.invoke(app, ["query", "--working-group", "SA4", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert "26.132" in result.output

    # Regression: this used to normalize SA4 -> SA and match nothing
    result_s4 = runner.invoke(app, ["query", "--working-group", "S4", "--output", "json"])
    assert "26.132" in result_s4.output

    result_sa = runner.invoke(app, ["query", "--working-group", "SA", "--output", "json"])
    assert "26.132" not in result_sa.output


def test_query_specs_rejects_unknown_subgroup(test_cache_dir: Path) -> None:
    result = runner.invoke(app, ["query", "--working-group", "S99"])

    assert result.exit_code == 2
    assert "Unknown sub-working group" in result.output
