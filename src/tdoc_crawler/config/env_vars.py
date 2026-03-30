"""
Environment variable name constants mapped to their corresponding config field paths.

All TDC_*, HTTP_CACHE_*, and LIGHTRAG_* environment variables remain functional
via pydantic's AliasChoices mechanism.

This module provides a StrEnum `ConfigEnvVar` where:
- Enum member names are the environment variable names (e.g., TDC_WORKING_GROUP)
- Enum member values are the TOML config field paths (e.g., "crawl.working_group")

Use these constants in CLI argument definitions to avoid hardcoding strings:
    # In args.py:
    from tdoc_crawler.config import ConfigEnvVar

    WorkingGroupOption = Annotated[
        list[str] | None,
        typer.Option("--working-group", envvar=ConfigEnvVar.TDC_WORKING_GROUP),
    ]
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class ConfigEnvVar(StrEnum):
    """Environment variable to TOML config field path mappings.

    Enum member names are env var names, values are config paths.
    Use member values (str) for pydantic validation_alias and
    member names for typer Option envvar parameter.
    """

    # Path/Cache (TDC_*)
    TDC_CACHE_DIR = "path.cache_dir"
    TDC_AI_STORE_PATH = "path.ai_cache_dir"
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
    # AI/LightRAG (TDC_AI_* and LIGHTRAG_*)
    TDC_AI_LLM_MODEL = "ai.llm_model"
    TDC_AI_LLM_API_BASE = "ai.llm_api_base"
    TDC_AI_LLM_API_KEY = "ai.llm_api_key"
    TDC_AI_EMBEDDING_MODEL = "ai.embedding_model"
    TDC_AI_EMBEDDING_API_BASE = "ai.embedding_api_base"
    TDC_AI_EMBEDDING_API_KEY = "ai.embedding_api_key"
    TDC_AI_MAX_CHUNK_SIZE = "ai.max_chunk_size"
    TDC_AI_CHUNK_OVERLAP = "ai.chunk_overlap"
    TDC_AI_CONVERT_PDF = "ai.convert_pdf"
    TDC_AI_CONVERT_MD = "ai.convert_md"
    TDC_AI_VLM = "ai.vlm"
    TDC_AI_ABSTRACT_MIN_WORDS = "ai.abstract_min_words"
    TDC_AI_ABSTRACT_MAX_WORDS = "ai.abstract_max_words"
    TDC_AI_PARALLELISM = "ai.parallelism"
    TDC_GRAPH_QUERY_LEVEL = "ai.graph_query_level"
    TDC_LIGHTRAG_SHARED_STORAGE = "ai.lightrag.shared_storage"
    LIGHTRAG_SHARED_STORAGE = "ai.lightrag.shared_storage"
    LIGHTRAG_DB_BACKEND = "ai.lightrag.db_backend"
    # AI-specific (not in settings.py but used in CLI args)
    TDC_AI_OUTPUT_FORMAT = "ai.output_format"
    TDC_LIMIT_MEETINGS = "crawl.limit_meetings"
    TDC_LIMIT_MEETINGS_PER_SUBWG = "crawl.limit_meetings_per_subwg"
    TDC_OVERALL_TIMEOUT = "crawl.overall_timeout"
    TDC_OUTPUT = "output_format"
    TDC_SOURCE_PATTERN = "crawl.source_pattern"
    TDC_SOURCE_PATTERN_EXCLUDE = "crawl.source_pattern_exclude"
    TDC_TITLE_PATTERN = "crawl.title_pattern"
    TDC_TITLE_PATTERN_EXCLUDE = "crawl.title_pattern_exclude"
    TDC_AGENDA_PATTERN = "crawl.agenda_pattern"
    TDC_AGENDA_PATTERN_EXCLUDE = "crawl.agenda_pattern_exclude"
    TDC_CHECKOUT = "crawl.checkout"
    TDC_CHECKOUT_DIR = "path.checkout_dir"
    TDC_VERBOSITY = "verbosity"
    TDC_USE_WHATTHESPEC = "http.use_whatthespec"
    TDC_AI_EMBEDDING_BACKEND = "ai.embedding_backend"
    TDC_AI_WORKSPACE_ACTIVATE = "ai.workspace_activate"
    TDC_AI_DEVICE = "ai.device"
    TDC_AI_NUM_THREADS = "ai.num_threads"
    TDC_AI_BATCH_SIZE = "ai.batch_size"


# Derived dict for backward compatibility (tools/docs that need dict form)
ENV_VAR_MAPPINGS: dict[str, str] = {e.name: e.value for e in ConfigEnvVar}


# Deprecated environment variables that will produce warnings.
# Format: "OLD_VAR": "Use NEW_VAR instead"
DEPRECATED_ENV_VARS: dict[str, str] = {}


def log_deprecation_warning(env_var_name: str) -> None:
    """Log a warning for a deprecated environment variable.

    Args:
        env_var_name: Name of the deprecated environment variable.
    """
    if env_var_name in DEPRECATED_ENV_VARS:
        replacement = DEPRECATED_ENV_VARS[env_var_name]
        logger.warning(
            "Environment variable '%s' is deprecated. %s",
            env_var_name,
            replacement,
        )
    else:
        logger.debug(
            "Environment variable '%s' is set but has no documented mapping",
            env_var_name,
        )


__all__ = [
    "DEPRECATED_ENV_VARS",
    "ENV_VAR_MAPPINGS",
    "ConfigEnvVar",
    "log_deprecation_warning",
]
