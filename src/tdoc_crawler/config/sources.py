"""Configuration file discovery, loading, and merging.

Implements mise-style config hierarchy with TOML, YAML, JSON support.

Precedence (highest to lowest):
1. CLI option value (explicit --config)
2. Discovered config files (later override earlier)
3. Environment variables (TDC_*)
4. Hard-coded defaults

Discovery Order (lowest to highest precedence):
- Global: ~/.config/3gpp-crawler/config.toml
- Global conf.d: ~/.config/3gpp-crawler/conf.d/*.toml (alphabetical)
- Project-level (CWD relative):
  - .config/.3gpp-crawler/conf.d/*.toml
  - .config/.3gpp-crawler/config.toml
  - .config/3gpp-crawler.toml
  - .3gpp-crawler/config.toml
  - .3gpp-crawler.toml
  - 3gpp-crawler.toml (highest project precedence)
"""

from __future__ import annotations

import json
import os
import re
from importlib import import_module
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    # Python < 3.11 fallback; install tomli in that case
    import tomli as tomllib  # type: ignore[no-redef]


class ConfigLoadError(Exception):
    """Raised when a config file cannot be loaded or parsed.

    Attributes:
        config_file: Path to the file that failed to load.
        reason: Human-readable explanation of the failure.
    """

    def __init__(self, config_file: Path, reason: str) -> None:
        self.config_file = config_file
        self.reason = reason
        super().__init__(f"Failed to load config from {config_file}: {reason}")


def discover_config_files(cwd: Path | None = None) -> list[Path]:
    """Discover configuration files in precedence order (lowest first).

    Searches standard locations for TOML, YAML, and JSON config files.
    Missing directories or files are silently skipped.

    Args:
        cwd: Working directory for project-level config search.
             Defaults to current working directory.

    Returns:
        List of Path objects in discovery order (lowest precedence first).
    """
    if cwd is None:
        cwd = Path.cwd()
    home = Path.home()
    global_dir = home / ".config" / "3gpp-crawler"

    files: list[Path] = []

    # Global configs (lowest precedence)
    _add_if_exists(global_dir / "config.toml", files)
    _collect_conf_d(global_dir / "conf.d", files)

    # Project-level configs (CWD relative, higher precedence)
    _collect_conf_d(cwd / ".config" / ".3gpp-crawler" / "conf.d", files)
    _add_if_exists(cwd / ".config" / ".3gpp-crawler" / "config.toml", files)
    _add_if_exists(cwd / ".config" / "3gpp-crawler.toml", files)
    _add_if_exists(cwd / ".3gpp-crawler" / "config.toml", files)
    _add_if_exists(cwd / ".3gpp-crawler.toml", files)
    _add_if_exists(cwd / "3gpp-crawler.toml", files)

    return files


def _collect_conf_d(directory: Path, files: list[Path]) -> None:
    """Append alphabetically sorted config files from a conf.d directory."""
    if not directory.is_dir():
        return
    files.extend(conf_file for conf_file in sorted(directory.iterdir()) if conf_file.suffix.lower() in {".toml", ".yaml", ".yml", ".json"})


def _add_if_exists(path: Path, files: list[Path]) -> None:
    """Append path to files list if it exists as a regular file."""
    if path.is_file():
        files.append(path)


def load_config_file(config_file: Path) -> dict[str, Any]:
    """Load a single config file and return its contents as a dict.

    Supports TOML (.toml), YAML (.yaml, .yml), and JSON (.json) formats.
    Environment variable interpolation is applied to string values.

    Args:
        config_file: Path to the config file.

    Returns:
        Dictionary of config values. Empty dict if file not found.

    Raises:
        ConfigLoadError: If the file cannot be parsed or has permission issues.
    """
    if not config_file.is_file():
        return {}

    suffix = config_file.suffix.lower()
    _loaders = {
        ".toml": _load_toml,
        ".yaml": _load_yaml,
        ".yml": _load_yaml,
        ".json": _load_json,
    }

    loader = _loaders.get(suffix)
    if loader is None:
        raise ConfigLoadError(config_file, f"Unsupported file format: {suffix}")

    try:
        data = loader(config_file)
    except FileNotFoundError:
        return {}
    except PermissionError as e:
        raise ConfigLoadError(config_file, f"Permission denied: {e}") from e
    except (ValueError, json.JSONDecodeError) as e:
        raise ConfigLoadError(config_file, f"Parse error: {e}") from e
    except ImportError as e:
        if "yaml" in str(e):
            raise ConfigLoadError(config_file, "PyYAML is required for YAML files but is not installed") from e
        raise

    if not isinstance(data, dict):
        raise ConfigLoadError(config_file, f"Expected dict at root, got {type(data).__name__}")

    return data


def _load_toml(config_file: Path) -> dict[str, Any]:
    """Load and interpolate a TOML config file."""
    with config_file.open("r", encoding="utf-8") as f:
        content = f.read()
    content = _interpolate_env_vars(content)
    return tomllib.loads(content)


def _load_yaml(config_file: Path) -> dict[str, Any]:
    """Load and interpolate a YAML config file."""
    yaml = import_module("yaml")
    with config_file.open("r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.scanner.ScannerError as e:
            raise ConfigLoadError(config_file, f"Parse error: {e}") from e
    if data is None:
        data = {}
    return _interpolate_env_vars(data)


def _load_json(config_file: Path) -> dict[str, Any]:
    """Load and interpolate a JSON config file."""
    with config_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _interpolate_env_vars(data)


def _interpolate_env_vars(value: Any) -> Any:
    """Recursively interpolate ${ENV_VAR} patterns in string values.

    Args:
        value: The value to interpolate (may be nested).

    Returns:
        The value with environment variables interpolated.
    """
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([^}]+)\}")

        def replacer(match: re.Match[str]) -> str:
            env_var = match.group(1)
            env_value = os.getenv(env_var)
            if env_value is None:
                return match.group(0)
            return env_value

        return pattern.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _interpolate_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env_vars(item) for item in value]
    return value


def merge_configs(configs: list[dict[str, Any]]) -> dict[str, Any]:
    """Deep merge multiple config dictionaries.

    Later configs override earlier ones. Nested dicts are merged recursively.
    Lists are replaced entirely (not appended).

    Args:
        configs: List of config dictionaries to merge, in precedence order
                 (lowest first, so later items override earlier).

    Returns:
        Merged configuration dictionary.

    Example:
        >>> merge_configs([{"path": {"cache_dir": "/default"}}, {"path": {"cache_dir": "/override"}}])
        {'path': {'cache_dir': '/override'}}
    """
    result: dict[str, Any] = {}

    for config in configs:
        if not config:
            continue
        result = _deep_merge(result, config)

    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Args:
        base: Base dictionary.
        override: Override dictionary (takes precedence).

    Returns:
        Merged dictionary.
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


__all__ = [
    "ConfigLoadError",
    "discover_config_files",
    "load_config_file",
    "merge_configs",
]
