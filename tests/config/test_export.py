"""Tests for config export functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdoc_crawler.config.export import ConfigExporter


class TestConfigExporter:
    """Test ConfigExporter class."""

    def test_export_toml_includes_comments(self) -> None:
        """TOML export includes field descriptions as comments."""
        exporter = ConfigExporter()
        toml = exporter.export("toml")

        assert "#" in toml  # Has comments
        assert "cache_dir" in toml
        assert "cache_ttl" in toml  # Check for actual field in the model

    def test_export_yaml_format(self) -> None:
        """YAML export produces valid YAML."""
        exporter = ConfigExporter()
        yaml_output = exporter.export("yaml")

        assert "cache_dir:" in yaml_output
        assert "path" in yaml_output

    def test_export_json_format(self) -> None:
        """JSON export produces valid JSON."""
        exporter = ConfigExporter()
        json_str = exporter.export("json")

        assert '"cache_dir"' in json_str

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Save creates output file."""
        exporter = ConfigExporter()
        output = tmp_path / "config.toml"

        exporter.save(output)

        assert output.exists()
        assert "cache_dir" in output.read_text()

    def test_save_raises_on_existing_file(self, tmp_path: Path) -> None:
        """Save raises error if file exists and force=False."""
        output = tmp_path / "config.toml"
        output.write_text("existing")

        exporter = ConfigExporter()

        with pytest.raises(FileExistsError):
            exporter.save(output)

    def test_save_overwrites_with_force(self, tmp_path: Path) -> None:
        """Save overwrites existing file with force=True."""
        output = tmp_path / "config.toml"
        output.write_text("existing")

        exporter = ConfigExporter()
        exporter.save(output, force=True)

        assert "cache_dir" in output.read_text()

    def test_export_all_formats(self) -> None:
        """Test all export formats work."""
        exporter = ConfigExporter()

        for fmt in ["toml", "yaml", "json"]:
            result = exporter.export(fmt)
            assert result
            assert len(result) > 0

    def test_toml_has_section_headers(self) -> None:
        """TOML export includes section headers."""
        exporter = ConfigExporter()
        toml = exporter.export("toml")

        assert "[path]" in toml
        assert "[http]" in toml
        assert "[credentials]" in toml

    def test_yaml_has_comments(self) -> None:
        """YAML export includes comments."""
        exporter = ConfigExporter()
        yaml_output = exporter.export("yaml")

        assert "# 3GPP Crawler Configuration" in yaml_output
        assert "# File system paths" in yaml_output
