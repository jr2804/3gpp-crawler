"""3GPP portal metadata fetcher for specs."""

import logging
from urllib.parse import parse_qs, urlparse

import requests

from tdoc_crawler.specs.normalization import normalize_spec_number

_logger = logging.getLogger(__name__)


class SpecNotFoundError(Exception):
    """Raised when a specification is not found on 3GPP portal."""

    pass


def fetch_threegpp_metadata(spec_number: str) -> dict[str, object]:
    """Fetch spec metadata via 3GPP.org redirect flow.

    Args:
        spec_number: Spec number to fetch (e.g., "26.131").

    Returns:
        Dictionary containing spec metadata from 3GPP portal.

    Raises:
        SpecNotFoundError: If the spec does not exist (redirects to unknown spec page).
        requests.HTTPError: If the HTTP request fails.
    """
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = f"https://www.3gpp.org/dynareport/{compact}.htm"

    response = requests.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()

    parsed = urlparse(response.url)
    query = parse_qs(parsed.query)
    spec_id = query.get("specificationId", [None])[0]

    # Verify the spec exists by checking for specificationId in the redirect URL
    if spec_id is None:
        _logger.warning("Spec %s not found (no specificationId in redirect URL: %s)", normalized, response.url)
        raise SpecNotFoundError(f"Spec {normalized} not found on 3GPP portal")

    payload: dict[str, object]
    try:
        payload = response.json()
    except ValueError:
        payload = {}

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
