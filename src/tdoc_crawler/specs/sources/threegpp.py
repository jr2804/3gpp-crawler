"""3GPP portal metadata fetcher for specs."""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.constants.urls import SPEC_DYNAREPORT_URL_TEMPLATE
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.normalization import normalize_spec_number

_logger = get_logger(__name__)


class SpecNotFoundError(Exception):
    """Raised when a specification is not found on 3GPP portal."""


def fetch_threegpp_metadata(spec_number: str, http_config: HttpConfig | None = None, http_cache_file: Path | None = None) -> dict[str, object]:
    """Fetch spec metadata via 3GPP.org redirect flow.

    Args:
        spec_number: Spec number to fetch (e.g., "26.131").
        http_config: Optional HTTP configuration from ThreeGPPConfig
        http_cache_file: Optional explicit path to the HTTP cache database.

    Returns:
        Dictionary containing spec metadata from 3GPP portal.

    Raises:
        SpecNotFoundError: If the spec does not exist (redirects to unknown spec page).
        requests.HTTPError: If the HTTP request fails.
    """
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = SPEC_DYNAREPORT_URL_TEMPLATE.format(compact=compact)

    session = create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()

    parsed = urlparse(response.request.url)
    query = parse_qs(parsed.query)
    spec_id = query.get("specificationId", [None])[0]

    # Verify the spec exists by checking for specificationId in the redirect URL
    if spec_id is None:
        _logger.warning("Spec %s not found (no specificationId in redirect URL: %s)", normalized, response.url)
        msg = f"Spec {normalized} not found on 3GPP portal"
        raise SpecNotFoundError(msg)

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
        "source_identifier": int(spec_id),
        "metadata_payload": payload,
        "versions": versions,
    }
