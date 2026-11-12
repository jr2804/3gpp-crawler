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
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time
from importlib import import_module
from pathlib import Path

from tdoc_crawler.utils.json_types import JSONScalar

try:
    import tomllib
except ImportError:
    # Python < 3.11 fallback; install tomli in that case
    import tomli as tomllib  # type: ignore[no-redef]

type ConfigValue = JSONScalar | date | datetime | time | Sequence[ConfigValue] | Mapping[str, ConfigValue]
"""A value that can appear in a configuration file (TOML, YAML or JSON)."""

type ConfigSection = Mapping[str, ConfigValue]
"""One configuration section (e.g. ``[http]``) with its keys and values."""

type ConfigDocument = Mapping[str, ConfigValue]
"""A parsed configuration file: top-level keys mapped to their values."""


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


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


def load_config_file(config_file: Path) -> ConfigDocument:
    """Load a single config file and return its contents as a dict.

    Supports TOML (.toml), YAML (.yaml, .yml), and JSON (.json) formats.
    Environment variable interpolation is applied to string values.

    Args:
        config_file: Path to the config file.

    Returns:
        Dictionary of config sections. Empty dict if file not found.

    Raises:
        ConfigLoadError: If the file cannot be parsed or has permission issues.
    """
    if not config_file.is_file():
        return {}

    suffix = config_file.suffix.lower()
    _loaders: dict[str, Callable[[Path], ConfigValue]] = {
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

    return _to_config_document(config_file, data)


def _to_config_document(config_file: Path, data: ConfigValue) -> ConfigDocument:
    """Narrow parsed config data to the document shape.

    Args:
        config_file: Path of the file the data came from (for error messages).
        data: Parsed configuration data.

    Returns:
        The configuration document.

    Raises:
        ConfigLoadError: If the root is not a mapping.
    """
    if not isinstance(data, dict):
        raise ConfigLoadError(config_file, f"Expected dict at root, got {type(data).__name__}")
    return data


def _load_toml(config_file: Path) -> ConfigValue:
    """Load and interpolate a TOML config file."""
    with config_file.open("r", encoding="utf-8") as f:
        content = f.read()
    content = _interpolate_env_text(content)
    return _coerce_config_value(tomllib.loads(content))


def _load_yaml(config_file: Path) -> ConfigValue:
    """Load and interpolate a YAML config file."""
    yaml = import_module("yaml")
    with config_file.open("r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.scanner.ScannerError as e:
            raise ConfigLoadError(config_file, f"Parse error: {e}") from e
    if data is None:
        data = {}
    return _interpolate_env_vars(_coerce_config_value(data))


def _load_json(config_file: Path) -> ConfigValue:
    """Load and interpolate a JSON config file."""
    with config_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _interpolate_env_vars(_coerce_config_value(data))


def _coerce_config_value(value: object) -> ConfigValue:
    """Convert parsed config data into the precise config value shape.

    Args:
        value: Parsed configuration data of unknown provenance.

    Returns:
        The value converted to :data:`ConfigValue`.

    Raises:
        ValueError: If the data contains a type that config files cannot hold.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime, time)):
        return value
    if isinstance(value, list):
        return [_coerce_config_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _coerce_config_value(item) for key, item in value.items()}
    msg = f"Unsupported config value type: {type(value).__name__}"
    raise ValueError(msg)


def _interpolate_env_vars(value: ConfigValue) -> ConfigValue:
    """Recursively interpolate ${ENV_VAR} patterns in string values.

    Args:
        value: The value to interpolate (may be nested).

    Returns:
        The value with environment variables interpolated.
    """
    if isinstance(value, str):
        return _interpolate_env_text(value)
    if isinstance(value, dict):
        return {k: _interpolate_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env_vars(item) for item in value]
    return value


def _interpolate_env_text(text: str) -> str:
    """Interpolate ``${ENV_VAR}`` patterns in raw text.

    Args:
        text: Text that may contain ``${ENV_VAR}`` placeholders.

    Returns:
        The text with known environment variables substituted. Unknown
        variables are left untouched.
    """

    def replacer(match: re.Match[str]) -> str:
        env_var = match.group(1)
        env_value = os.getenv(env_var)
        if env_value is None:
            return match.group(0)
        return env_value

    return _ENV_VAR_PATTERN.sub(replacer, text)


def merge_configs(configs: list[ConfigDocument]) -> ConfigDocument:
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
    result: ConfigDocument = {}

    for config in configs:
        if not config:
            continue
        result = _deep_merge(result, config)

    return result


def _deep_merge(base: ConfigDocument, override: ConfigDocument) -> ConfigDocument:
    """Deep merge two configuration documents.

    Nested tables are merged recursively, lists are replaced entirely.

    Args:
        base: Base document.
        override: Override document (takes precedence).

    Returns:
        Merged document.
    """
    result = dict(base)

    for key, value in override.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _deep_merge(current, value)
        else:
            result[key] = value

    return result


__all__ = [
    "ConfigDocument",
    "ConfigLoadError",
    "ConfigSection",
    "ConfigValue",
    "discover_config_files",
    "load_config_file",
    "merge_configs",
]
