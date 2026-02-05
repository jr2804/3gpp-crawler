"""WhatTheSpec metadata fetcher."""

import requests

from tdoc_crawler.specs.normalization import normalize_spec_number


def fetch_whatthespec_metadata(spec_number: str) -> dict[str, object]:
    """Fetch spec metadata via whatthespec.net JSON API."""
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = f"https://whatthespec.net/api/specs/{compact}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()

    versions = payload.get("versions")
    if not isinstance(versions, list):
        versions = []

    return {
        "spec_number": normalized,
        "source_name": "whatthespec",
        "source_identifier": payload.get("id"),
        "metadata_payload": payload,
        "versions": versions,
    }
