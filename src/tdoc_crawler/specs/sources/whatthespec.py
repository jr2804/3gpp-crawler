"""WhatTheSpec metadata fetcher."""

from pathlib import Path

from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.models.base import DEFAULT_CACHE_DIR
from tdoc_crawler.specs.normalization import normalize_spec_number


def fetch_whatthespec_metadata(spec_number: str) -> dict[str, object]:
    """Fetch spec metadata via whatthespec.net JSON API."""
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = f"https://whatthespec.net/3gpp/spec.php?q={compact}&api=1"
    cache_dir: Path = DEFAULT_CACHE_DIR
    session = create_cached_session(cache_dir=cache_dir)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    metadata = {}

    if payload:
        payload = payload[0] if isinstance(payload, list) else payload

        # The API uses 'vers' for versions and 'specnum' for spec number
        versions = payload.get("vers", [])
        if not isinstance(versions, list):
            versions = []

        metadata = {
            "spec_number": normalized,
            "source_name": "whatthespec",
            "source_identifier": payload.get("specnum", normalized),
            "metadata_payload": payload,
            "versions": versions,
        }

    return metadata
