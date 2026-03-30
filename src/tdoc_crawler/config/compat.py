"""Backward compatibility layer for environment variable mapping.

This module provides mappings between legacy environment variable names and
their corresponding config field paths, enabling seamless migration from
env-var-based configuration to the new config-file-based approach.

All existing TDC_*, HTTP_CACHE_*, and LIGHTRAG_* environment variables
remain functional via pydantic's AliasChoices mechanism.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Maps environment variable names to their config field paths.
# Used for documentation and validation purposes.
ENV_VAR_MAPPINGS: dict[str, str] = {
    # Path/Cache (TDC_*)
    "TDC_CACHE_DIR": "path.cache_dir",
    "TDC_AI_STORE_PATH": "path.ai_cache_dir",
    # Credentials (TDC_*)
    "TDC_EOL_USERNAME": "credentials.username",
    "TDC_EOL_PASSWORD": "credentials.password",
    "TDC_EOL_PROMPT": "credentials.prompt",
    # HTTP/SQLite (overrides)
    "TDC_VERIFY_SSL": "http.verify_ssl",
    "TDC_TIMEOUT": "http.timeout",
    "TDC_MAX_RETRIES": "http.max_retries",
    # HTTP Cache (HTTP_CACHE_*)
    "HTTP_CACHE_TTL": "http.cache_ttl",
    "HTTP_CACHE_ENABLED": "http.cache_enabled",
    "HTTP_CACHE_REFRESH_ON_ACCESS": "http.cache_refresh_on_access",
    # Crawl filters (TDC_ prefixed)
    "TDC_WORKING_GROUP": "crawl.working_group",
    "TDC_SUB_GROUP": "crawl.sub_group",
    "TDC_START_DATE": "crawl.date_start",
    "TDC_END_DATE": "crawl.date_end",
    "TDC_SOURCE_LIKE": "crawl.source_like",
    "TDC_AGENDA_LIKE": "crawl.agenda_like",
    "TDC_TITLE_LIKE": "crawl.title_like",
    "TDC_LIMIT_TDOCS": "crawl.limit",
    "TDC_WORKERS": "crawl.workers",
    # AI/LightRAG (TDC_AI_* and LIGHTRAG_*)
    "TDC_AI_LLM_MODEL": "ai.llm_model",
    "TDC_AI_LLM_API_BASE": "ai.llm_api_base",
    "TDC_AI_LLM_API_KEY": "ai.llm_api_key",
    "TDC_AI_EMBEDDING_MODEL": "ai.embedding_model",
    "TDC_AI_EMBEDDING_API_BASE": "ai.embedding_api_base",
    "TDC_AI_EMBEDDING_API_KEY": "ai.embedding_api_key",
    "TDC_AI_MAX_CHUNK_SIZE": "ai.max_chunk_size",
    "TDC_AI_CHUNK_OVERLAP": "ai.chunk_overlap",
    "TDC_AI_CONVERT_PDF": "ai.convert_pdf",
    "TDC_AI_CONVERT_MD": "ai.convert_md",
    "TDC_AI_VLM": "ai.vlm",
    "TDC_AI_ABSTRACT_MIN_WORDS": "ai.abstract_min_words",
    "TDC_AI_ABSTRACT_MAX_WORDS": "ai.abstract_max_words",
    "TDC_AI_PARALLELISM": "ai.parallelism",
    "TDC_GRAPH_QUERY_LEVEL": "ai.graph_query_level",
    "TDC_LIGHTRAG_SHARED_STORAGE": "ai.lightrag.shared_storage",
    "LIGHTRAG_SHARED_STORAGE": "ai.lightrag.shared_storage",
    "LIGHTRAG_DB_BACKEND": "ai.lightrag.db_backend",
}

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
    "log_deprecation_warning",
]
