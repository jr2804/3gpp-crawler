"""3GPP portal metadata fetcher for specs."""

import logging
from urllib.parse import parse_qs, urlparse

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.utils.normalization import normalize_spec_number

_logger = logging.getLogger(__name__)


class SpecNotFoundError(Exception):
    """Raised when a specification is not found on 3GPP portal."""

    pass


def fetch_threegpp_metadata(spec_number: str, cache_manager_name: str | None = None) -> dict[str, object]:
    """Fetch spec metadata via 3GPP.org redirect flow.

    Args:
        spec_number: Spec number to fetch (e.g., "26.131").
        cache_manager_name: Optional name of cache manager to use for HTTP caching.

    Returns:
        Dictionary containing spec metadata from 3GPP portal.

    Raises:
        SpecNotFoundError: If the spec does not exist (redirects to unknown spec page).
        requests.HTTPError: If the HTTP request fails.
    """
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    url = f"https://www.3gpp.org/dynareport/{compact}.htm"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    }

    session = create_cached_session(resolve_cache_manager(cache_manager_name).root)
    response = session.get(url, timeout=30, allow_redirects=True, headers=headers)
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
