"""Unit tests for config export functionality."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config.export import ConfigExporter, FormatType
from tdoc_crawler.config.settings import ThreeGPPConfig


def test_config_exporter_initialization() -> None:
    """Test ConfigExporter initialization with defaults."""
    exporter = ConfigExporter()
    assert isinstance(exporter.config, ThreeGPPConfig)


def test_config_exporter_with_custom_config() -> None:
    """Test ConfigExporter with a provided config instance."""
    config = ThreeGPPConfig()
    exporter = ConfigExporter(config)
    assert exporter.config is config


def test_export_toml() -> None:
    """Test exporting configuration to TOML format."""
    exporter = ConfigExporter()
    toml_output = exporter.export("toml")
    assert isinstance(toml_output, str)
    # Check for some expected TOML content
    assert "cache_dir" in toml_output
    assert "http" in toml_output


def test_export_yaml() -> None:
    """Test exporting configuration to YAML format."""
    exporter = ConfigExporter()
    yaml_output = exporter.export("yaml")
    assert isinstance(yaml_output, str)
    assert "cache_dir" in yaml_output


def test_export_json() -> None:
    """Test exporting configuration to JSON format."""
    exporter = ConfigExporter()
    json_output = exporter.export("json")
    assert isinstance(json_output, str)
    assert "cache_dir" in json_output


def test_save_to_file(tmp_path: Path) -> None:
    """Test saving configuration to a file."""
    exporter = ConfigExporter()
    output_path = tmp_path / "config.toml"
    exporter.save(output_path, "toml")
    assert output_path.exists()
    content = output_path.read_text()
    assert "cache_dir" in content


def test_save_overwrite(tmp_path: Path) -> None:
    """Test overwriting an existing file with force=True."""
    exporter = ConfigExporter()
    output_path = tmp_path / "config.yaml"
    # Create a dummy file
    output_path.write_text("dummy")
    exporter.save(output_path, "yaml", force=True)
    assert output_path.exists()
    content = output_path.read_text()
    assert "cache_dir" in content


def test_unsupported_format_raises() -> None:
    """Test that unsupported format raises ValueError."""
    exporter = ConfigExporter()
    # Use a type ignore to bypass static type checking for invalid format
    invalid_format: FormatType = "invalid"  # type: ignore[assignment]
    try:
        exporter.export(invalid_format)
    except ValueError as e:
        assert "Unsupported format" in str(e)
    else:
        raise AssertionError("Expected ValueError for unsupported format")
