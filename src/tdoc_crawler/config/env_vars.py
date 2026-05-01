"""Environment variable name constants mapped to their corresponding config field paths.

All TDC_* and HTTP_CACHE_* environment variables remain functional
via pydantic's AliasChoices mechanism.

This module provides a StrEnum `ConfigEnvVar` where:
- Enum member names are the environment variable names (e.g., TDC_WORKING_GROUP)
- Enum member values are the TOML config field paths (e.g., "crawl.working_group")

Use these constants in CLI argument definitions to avoid hardcoding strings:
    # In args.py:
    from tdoc_crawler.config import ConfigEnvVar

    WorkingGroupOption = Annotated[
        list[str] | None,
        typer.Option("--working-group", envvar=ConfigEnvVar.TDC_WORKING_GROUP.name),
    ]
"""

from __future__ import annotations

from enum import StrEnum


class ConfigEnvVar(StrEnum):
    """Environment variable to TOML config field path mappings.

    Enum member names are env var names, values are config paths.
    Use member values (str) for pydantic validation_alias and
    member names for typer Option envvar parameter.
    """

    # Path/Cache (TDC_*)
    TDC_CACHE_DIR = "path.cache_dir"
    # Credentials (TDC_*)
    TDC_EOL_USERNAME = "credentials.username"
    TDC_EOL_PASSWORD = "credentials.password"  # noqa: S105
    TDC_EOL_PROMPT = "credentials.prompt"
    # HTTP/SQLite (overrides)
    TDC_VERIFY_SSL = "http.verify_ssl"
    TDC_TIMEOUT = "http.timeout"
    TDC_MAX_RETRIES = "http.max_retries"
    # HTTP Cache (HTTP_CACHE_*)
    HTTP_CACHE_TTL = "http.cache_ttl"
    HTTP_CACHE_ENABLED = "http.cache_enabled"
    HTTP_CACHE_REFRESH_ON_ACCESS = "http.cache_refresh_on_access"
    # Crawl filters (TDC_ prefixed)
    TDC_WORKING_GROUP = "crawl.working_group"
    TDC_SUB_GROUP = "crawl.sub_group"
    TDC_START_DATE = "crawl.date_start"
    TDC_END_DATE = "crawl.date_end"
    TDC_SOURCE_LIKE = "crawl.source_like"
    TDC_AGENDA_LIKE = "crawl.agenda_like"
    TDC_TITLE_LIKE = "crawl.title_like"
    TDC_LIMIT_TDOCS = "crawl.limit"
    TDC_WORKERS = "crawl.workers"
    TDC_LIMIT_MEETINGS = "crawl.limit_meetings"
    TDC_LIMIT_MEETINGS_PER_SUBWG = "crawl.limit_meetings_per_subwg"
    TDC_OUTPUT = "output_format"
    TDC_SOURCE_PATTERN = "crawl.source_pattern"
    TDC_SOURCE_PATTERN_EXCLUDE = "crawl.source_pattern_exclude"
    TDC_TITLE_PATTERN = "crawl.title_pattern"
    TDC_TITLE_PATTERN_EXCLUDE = "crawl.title_pattern_exclude"
    TDC_AGENDA_PATTERN = "crawl.agenda_pattern"
    TDC_AGENDA_PATTERN_EXCLUDE = "crawl.agenda_pattern_exclude"
    TDC_CHECKOUT = "crawl.checkout"
    TDC_CHECKOUT_DIR = "path.checkout_dir"
    TDC_WORKSPACES_DIR = "path.workspaces_dirname"
    TDC_VERBOSITY = "verbosity"
    TDC_USE_WHATTHESPEC = "http.use_whatthespec"


TOML_PATH_TO_ENV_VAR: dict[str, str] = {e.value: e.name for e in ConfigEnvVar}


__all__ = [
    "TOML_PATH_TO_ENV_VAR",
    "ConfigEnvVar",
]
