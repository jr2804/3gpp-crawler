"""Tests for config file discovery."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from tdoc_crawler.config.sources import (
    ConfigLoadError,
    discover_config_files,
    load_config_file,
    merge_configs,
)


class TestDiscoverConfigFiles:
    """Test discover_config_files function."""

    def test_returns_empty_list_when_no_configs(self, tmp_path: Path) -> None:
        """Returns empty list when no config files exist."""
        files = discover_config_files(cwd=tmp_path)
        assert files == []

    def test_finds_toml_in_global_config_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Finds config.toml in ~/.config/3gpp-crawler/."""
        global_config = Path.home() / ".config" / "3gpp-crawler"
        global_config.mkdir(parents=True, exist_ok=True)
        config_file = global_config / "config.toml"
        config_file.write_text("[http]\ncache_ttl = 7200")

        try:
            files = discover_config_files(cwd=tmp_path)
            assert config_file in files
        finally:
            config_file.unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                global_config.rmdir()

    def test_finds_project_level_config(self, tmp_path: Path) -> None:
        """Finds 3gpp-crawler.toml in project root."""
        project_config = tmp_path / "3gpp-crawler.toml"
        project_config.write_text("[http]\ncache_ttl = 7200")

        files = discover_config_files(cwd=tmp_path)
        assert project_config in files

    def test_discovery_order_lowest_to_highest(self, tmp_path: Path) -> None:
        """Returns files in discovery order (lowest to highest precedence)."""
        # Create configs at different levels
        global_config = Path.home() / ".config" / "3gpp-crawler" / "config.toml"
        global_config.parent.mkdir(parents=True, exist_ok=True)
        global_config.write_text("[global]\nvalue = 1")

        project_config = tmp_path / "3gpp-crawler.toml"
        project_config.write_text("[project]\nvalue = 2")

        try:
            files = discover_config_files(cwd=tmp_path)
            # Global should come before project
            global_idx = next(i for i, f in enumerate(files) if f == global_config)
            project_idx = next(i for i, f in enumerate(files) if f == project_config)
            assert global_idx < project_idx
        finally:
            global_config.unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                global_config.parent.rmdir()

    def test_conf_d_files_alphabetically_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """conf.d files are sorted alphabetically."""
        conf_d = Path.home() / ".config" / "3gpp-crawler" / "conf.d"
        conf_d.mkdir(parents=True, exist_ok=True)

        # Create files in reverse alphabetical order
        z_file = conf_d / "z_config.toml"
        a_file = conf_d / "a_config.toml"
        z_file.write_text("[z]\nvalue = 1")
        a_file.write_text("[a]\nvalue = 2")

        try:
            files = discover_config_files(cwd=tmp_path)
            conf_d_files = [f for f in files if f.parent == conf_d]
            names = [f.name for f in conf_d_files]
            assert names == sorted(names)
        finally:
            z_file.unlink(missing_ok=True)
            a_file.unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                conf_d.rmdir()

    def test_finds_yaml_and_json_in_conf_d(self, tmp_path: Path) -> None:
        """Finds .yaml, .yml, and .json files in conf.d directories."""
        # Create conf.d with various config file types
        # Note: discovery uses .config/.3gpp-crawler/conf.d (with extra .3gpp-crawler)
        conf_d = tmp_path / ".config" / ".3gpp-crawler" / "conf.d"
        conf_d.mkdir(parents=True)

        (conf_d / "config.yaml").write_text("key: value")
        (conf_d / "settings.yml").write_text("setting: true")
        (conf_d / "config.json").write_text('{"key": "value"}')

        files = discover_config_files(cwd=tmp_path)

        assert any(f.name == "config.yaml" for f in files)
        assert any(f.name == "settings.yml" for f in files)
        assert any(f.name == "config.json" for f in files)


class TestLoadConfigFile:
    """Test load_config_file function."""

    def test_loads_toml_file(self, tmp_path: Path) -> None:
        """Loads TOML file correctly."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[http]\ncache_ttl = 7200\ncache_enabled = true")

        result = load_config_file(config_file)

        assert result["http"]["cache_ttl"] == 7200
        assert result["http"]["cache_enabled"] is True

    def test_loads_yaml_file(self, tmp_path: Path) -> None:
        """Loads YAML file correctly."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("http:\n  cache_ttl: 7200\n  cache_enabled: true")

        result = load_config_file(config_file)

        assert result["http"]["cache_ttl"] == 7200
        assert result["http"]["cache_enabled"] is True

    def test_loads_json_file(self, tmp_path: Path) -> None:
        """Loads JSON file correctly."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"http": {"cache_ttl": 7200}}')

        result = load_config_file(config_file)

        assert result["http"]["cache_ttl"] == 7200

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path) -> None:
        """Returns empty dict for non-existent file."""
        result = load_config_file(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_raises_error_for_invalid_toml(self, tmp_path: Path) -> None:
        """Raises ConfigLoadError for invalid TOML."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("invalid toml [[[")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config_file(config_file)

        assert "Parse error" in str(exc_info.value)

    def test_raises_error_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Raises ConfigLoadError for invalid YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config_file(config_file)

        assert "Parse error" in str(exc_info.value)

    def test_raises_error_for_invalid_json(self, tmp_path: Path) -> None:
        """Raises ConfigLoadError for invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json}")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config_file(config_file)

        assert "Parse error" in str(exc_info.value)

    def test_interpolates_env_vars_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Interpolates ${ENV_VAR} patterns in YAML files."""
        monkeypatch.setenv("TEST_CACHE_TTL", "9999")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("http:\n  cache_ttl: ${TEST_CACHE_TTL}")

        result = load_config_file(config_file)

        assert result["http"]["cache_ttl"] == "9999"

    def test_interpolates_env_vars_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Interpolates ${ENV_VAR} patterns in JSON files."""
        monkeypatch.setenv("TEST_CACHE_TTL", "9999")

        config_file = tmp_path / "config.json"
        config_file.write_text('{"http": {"cache_ttl": "${TEST_CACHE_TTL}"}}')

        result = load_config_file(config_file)

        assert result["http"]["cache_ttl"] == "9999"

    def test_interpolates_missing_env_var_as_literal(self, tmp_path: Path) -> None:
        """Missing env vars are left as-is."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("http:\n  cache_ttl: ${NONEXISTENT_VAR}")

        result = load_config_file(config_file)

        assert result["http"]["cache_ttl"] == "${NONEXISTENT_VAR}"


class TestMergeConfigs:
    """Test merge_configs function."""

    def test_returns_empty_dict_for_empty_list(self) -> None:
        """Returns empty dict for empty input."""
        result = merge_configs([])
        assert result == {}

    def test_single_config_unchanged(self) -> None:
        """Single config dict is returned unchanged."""
        config = {"http": {"cache_ttl": 7200}}
        result = merge_configs([config])
        assert result == config

    def test_later_overrides_earlier(self) -> None:
        """Later configs override earlier values."""
        result = merge_configs(
            [
                {"http": {"cache_ttl": 3600}},
                {"http": {"cache_ttl": 7200}},
            ]
        )
        assert result["http"]["cache_ttl"] == 7200

    def test_deep_merge_nested_dicts(self) -> None:
        """Nested dicts are merged recursively."""
        result = merge_configs(
            [
                {"path": {"cache_dir": "/default", "db_file": "db.sqlite"}},
                {"path": {"cache_dir": "/override"}},
            ]
        )
        assert result["path"]["cache_dir"] == "/override"
        assert result["path"]["db_file"] == "db.sqlite"

    def test_lists_are_replaced_not_appended(self) -> None:
        """Lists are replaced entirely, not merged."""
        result = merge_configs(
            [
                {"items": [1, 2, 3]},
                {"items": [4, 5]},
            ]
        )
        assert result["items"] == [4, 5]

    def test_skips_empty_dicts(self) -> None:
        """Empty dicts in list are skipped."""
        result = merge_configs(
            [
                {"http": {"cache_ttl": 7200}},
                {},
                {"http": {"cache_ttl": 9999}},
            ]
        )
        assert result["http"]["cache_ttl"] == 9999

    def test_new_keys_added_from_later_configs(self) -> None:
        """Keys from later configs are added if not present earlier."""
        result = merge_configs(
            [
                {"path": {"cache_dir": "/default"}},
                {"http": {"cache_ttl": 7200}},
            ]
        )
        assert "path" in result
        assert "http" in result
        assert result["http"]["cache_ttl"] == 7200


class TestConfigLoadError:
    """Test ConfigLoadError exception."""

    def test_error_message_includes_path(self, tmp_path: Path) -> None:
        """Error message includes the file path."""
        config_file = tmp_path / "config.toml"
        error = ConfigLoadError(config_file, "Parse error")

        assert str(config_file) in str(error)
        assert "Parse error" in str(error)

    def test_error_has_config_file_attribute(self, tmp_path: Path) -> None:
        """Error has config_file attribute with the problematic file."""
        config_file = tmp_path / "config.toml"
        error = ConfigLoadError(config_file, "Test reason")

        assert error.config_file == config_file
        assert error.reason == "Test reason"
