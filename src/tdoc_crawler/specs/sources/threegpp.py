"""3GPP portal metadata fetcher for specs."""

import logging
from urllib.parse import parse_qs, urlparse

import requests

from tdoc_crawler.specs.normalization import normalize_spec_number

_logger = logging.getLogger(__name__)


def fetch_threegpp_metadata(spec_number: str) -> dict[str, object]:
    """Fetch spec metadata via 3GPP.org redirect flow."""
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = f"https://www.3gpp.org/specs/{compact}"

    response = requests.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()

    parsed = urlparse(response.url)
    query = parse_qs(parsed.query)
    spec_id = None
    if "specificationId" in query:
        spec_id = query["specificationId"][0]

    payload: dict[str, object]
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if spec_id is None:
        _logger.debug("No specificationId found in redirect URL: %s", response.url)

    versions = payload.get("versions")
    if not isinstance(versions, list):
        versions = []

    return {
        "spec_number": normalized,
        "source_name": "3gpp",
        "source_identifier": spec_id,
        "metadata_payload": payload,
        "versions": versions,
    }
