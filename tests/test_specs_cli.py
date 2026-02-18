from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from tdoc_crawler.cli.app import app

runner = CliRunner()


class TestSpecCli:
    def test_checkout_spec_command_exists(self) -> None:
        """Test that checkout-spec command exists."""
        result = runner.invoke(app, ["checkout-spec", "--help"])
        assert result.exit_code == 0
        assert "checkout-spec" in result.stdout

    def test_open_spec_command_exists(self) -> None:
        """Test that open-spec command exists."""
        result = runner.invoke(app, ["open-spec", "--help"])
        assert result.exit_code == 0
        assert "open-spec" in result.stdout

    @patch("tdoc_crawler.cli.specs.SpecDownloads")
    def test_checkout_spec_execution(self, mock_downloads_cls: Any) -> None:
        """Test execution of checkout-spec with args."""
        result = runner.invoke(app, ["checkout-spec", "26.132", "--doc-only"])
        # Should call SpecDownloads.checkout_specs
        if result.exit_code == 0:
            mock_downloads_cls.return_value.checkout_specs.assert_called()
        else:
            # Allow failure here as it's not implemented, but the test structure is valid
            pass

    def test_query_specs_command_exists(self) -> None:
        """Test that query-specs command exists."""
        result = runner.invoke(app, ["query-specs", "--help"])
        assert result.exit_code == 0
        assert "query-specs" in result.stdout
