"""Tests for settings loaded from a config file."""

from __future__ import annotations

from pathlib import Path

from tdoc_crawler.config.settings import ExtractConfig, ThreeGPPConfig


class TestExtractConfigDefaults:
    """The shipped extraction defaults match the documented behaviour."""

    def test_flattens_single_folder_archives(self) -> None:
        assert ExtractConfig().flatten_single_root is True

    def test_excludes_version_control_directories(self) -> None:
        assert ".git/" in ExtractConfig().exclude
        assert ".hg/" in ExtractConfig().exclude
        assert ".svn/" in ExtractConfig().exclude


class TestExtractConfigFromFile:
    """``[extract]`` is file-only configuration (no env var, no CLI flag)."""

    def test_reads_flatten_switch_and_exclude_list(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """[extract]
flatten_single_root = false
exclude = [".git/", "*.log", "node_modules/"]
""",
            encoding="utf-8",
        )

        config = ThreeGPPConfig.from_settings(config_file=config_file)

        assert config.extract.flatten_single_root is False
        assert config.extract.exclude == [".git/", "*.log", "node_modules/"]

    def test_missing_section_keeps_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("[http]\ncache_ttl = 60\n", encoding="utf-8")

        config = ThreeGPPConfig.from_settings(config_file=config_file)

        assert config.extract.flatten_single_root is True
        assert config.extract.exclude == ExtractConfig().exclude
