"""WhatTheSpec metadata fetcher."""

from pathlib import Path

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.constants.urls import WHATSPEC_BASE_URL, WHATSPEC_SPEC_URL_TEMPLATE
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.specs.models import SpecMetadata
from tdoc_crawler.utils.json_types import coerce_json_value
from tdoc_crawler.utils.normalization import normalize_spec_number


def fetch_whatthespec_metadata(spec_number: str, http_config: HttpConfig | None = None, http_cache_file: Path | None = None) -> SpecMetadata:
    """Fetch spec metadata via whatthespec.net JSON API.

    Args:
        spec_number: Spec number to fetch (e.g., "26.131").
        http_config: Optional HTTP configuration from ThreeGPPConfig.
        http_cache_file: Optional explicit path to the HTTP cache database.

    Returns:
        Metadata for the spec; empty payload when the source has no entry.
    """
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = WHATSPEC_SPEC_URL_TEMPLATE.format(base=WHATSPEC_BASE_URL, compact=compact)
    session = create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    response = session.get(url, timeout=30)
    response.raise_for_status()

    payload = coerce_json_value(response.json())
    if isinstance(payload, list):
        payload = payload[0] if payload else None

    if not isinstance(payload, dict):
        return SpecMetadata(spec_number=normalized, source_name="whatthespec")

    # The API uses 'vers' for versions and 'specnum' for spec number
    versions = payload.get("vers", [])
    if not isinstance(versions, list):
        versions = []

    source_identifier = payload.get("specnum", normalized)
    if not isinstance(source_identifier, (str, int)):
        source_identifier = None

    return SpecMetadata(
        spec_number=normalized,
        source_name="whatthespec",
        source_identifier=source_identifier,
        metadata_payload=payload,
        versions=versions,
    )
