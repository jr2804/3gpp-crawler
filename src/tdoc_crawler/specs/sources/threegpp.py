"""3GPP portal metadata fetcher for specs.

Fetches spec metadata and version listings from the 3GPP portal
via the dynareport redirect. This is the primary and authoritative
source for spec metadata and version information.

Flow:
  1. Fetch ``https://www.3gpp.org/dynareport/{compact}.htm``
  2. Follow redirect to the portal specification details page
  3. Parse the portal HTML for metadata (General, Responsibility tabs)
     and version listings (Versions tab)
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.normalization import normalize_spec_number

_logger = get_logger(__name__)

# Release letter → major version mapping (Rel-10 through Rel-20+)
# Kept as utility for filename-based version decoding elsewhere.
_RELEASE_LETTER_MAP: dict[str, int] = {
    "a": 10,
    "b": 11,
    "c": 12,
    "d": 13,
    "e": 14,
    "f": 15,
    "g": 16,
    "h": 17,
    "i": 18,
    "j": 19,
    "k": 20,
}

_DYNAREPORT_URL = "https://www.3gpp.org/dynareport/{compact}.htm"

# ---------------------------------------------------------------------------
# Regex patterns for parsing the portal spec details page
# ---------------------------------------------------------------------------

# General tab — stable element IDs
_RE_TITLE = re.compile(r'<span id="titleVal">([^<]+)</span>')
_RE_STATUS = re.compile(r'<span id="statusVal">([^<]+)</span>')
_RE_TYPE = re.compile(r'<span id="typeVal">([^<]+)</span>')

# Responsibility tab — primary working group
_RE_PRIMARY_GROUP = re.compile(
    r'PrimaryResponsibleGroupLbl.*?<span>\s*([^<]+?)\s*</span>',
    re.DOTALL,
)

# Versions tab — download links with version text
# <a id="..._lnkFtpDownload" ... href=".../26260-j10.zip">19.1.0</a>
_RE_VERSION_LINK = re.compile(
    r'<a\s[^>]*id="[^"]*_lnkFtpDownload"[^>]*href="([^"]+)"[^>]*>'
    r'\s*(\d+\.\d+\.\d+)\s*</a>',
    re.IGNORECASE,
)


class SpecNotFoundError(Exception):
    """Raised when a specification is not found on the 3GPP portal."""

    pass


# ---------------------------------------------------------------------------
# Utility: filename-based version decoding (for FTP archives)
# ---------------------------------------------------------------------------

# Regex for 3GPP spec zip filenames from FTP archive:
#   {compact}-{version_code}.zip
_SPEC_FILE_RE = re.compile(
    r"^(?P<compact>\d{5})-(?P<vercode>[a-z]\d{2}|\d{3})\.zip$",
    re.IGNORECASE,
)


def _decode_version_from_filename(compact: str, filename: str) -> str | None:
    """Decode a 3GPP FTP archive filename to a version string.

    Filename format: ``{compact}-{vercode}.zip``

    Version code encoding:
      - Rel >= 10: one letter (release) + two digits (minor, editorial)
        e.g., ``j10`` → release 19, minor 1, editorial 0 → ``19.1.0``
      - Rel < 10: three digits (major, minor, editorial)
        e.g., ``100`` → ``1.0.0``

    Args:
        compact: Five-digit compact spec number (e.g., "26260").
        filename: Filename from the FTP directory (e.g., "26260-j10.zip").

    Returns:
        Version string (e.g., "19.1.0") or None if the filename cannot be decoded.
    """
    match = _SPEC_FILE_RE.match(filename)
    if not match or match.group("compact") != compact:
        return None

    vercode = match.group("vercode").lower()

    # Rel >= 10: letter + two digits
    if vercode[0].isalpha():
        release = _RELEASE_LETTER_MAP.get(vercode[0])
        if release is None:
            return None
        minor = int(vercode[1])
        editorial = int(vercode[2])
        return f"{release}.{minor}.{editorial}"

    # Rel < 10: three digits
    return f"{int(vercode[0])}.{int(vercode[1])}.{int(vercode[2])}"


# ---------------------------------------------------------------------------
# Portal HTML parsing
# ---------------------------------------------------------------------------


def _parse_spec_type(raw_type: str) -> str:
    """Normalize spec type from portal text to short form.

    Examples:
        "Technical specification (TS)" → "TS"
        "Technical Report (TR)" → "TR"
    """
    raw = raw_type.strip().upper()
    if "REPORT" in raw:
        return "TR"
    return "TS"


def _extract_filename_from_url(url: str) -> str:
    """Extract the zip filename from a full FTP URL."""
    return url.rsplit("/", maxsplit=1)[-1] if "/" in url else url


def _parse_portal_html(html: str, normalized: str) -> dict[str, object]:
    """Parse the 3GPP portal spec details page HTML.

    Extracts metadata from the General and Responsibility tabs,
    and version listings from the Versions tab.
    """
    # General tab
    title_match = _RE_TITLE.search(html)
    status_match = _RE_STATUS.search(html)
    type_match = _RE_TYPE.search(html)

    title = title_match.group(1).strip() if title_match else "Unknown"
    status = status_match.group(1).strip() if status_match else "unknown"
    raw_type = type_match.group(1).strip() if type_match else "Technical specification (TS)"
    spec_type = _parse_spec_type(raw_type)

    # Series from spec number
    series_prefix = normalized.split(".", maxsplit=1)[0]
    series = f"{series_prefix}_series"

    # Responsibility tab — working group
    wg_match = _RE_PRIMARY_GROUP.search(html)
    working_group = wg_match.group(1).strip() if wg_match else "unknown"
    # Normalize: "SA 4" → "SA4"
    working_group = re.sub(r"\s+", "", working_group)

    # Versions tab — all download links with version text
    version_links = _RE_VERSION_LINK.findall(html)

    if not version_links:
        return {
            "has_versions": False,
            "title": title,
            "spec_type": spec_type,
            "status": status,
            "working_group": working_group,
            "series": series,
        }

    # Build (version, filename) pairs, sort descending by version
    entries: list[tuple[str, str]] = []
    for url, version_text in version_links:
        filename = _extract_filename_from_url(url)
        entries.append((version_text, filename))

    entries.sort(key=lambda e: Version(e[0]), reverse=True)

    versions = [e[0] for e in entries]
    spec_files = [e[1] for e in entries]
    latest_version = versions[0] if versions else None

    return {
        "has_versions": True,
        "title": title,
        "spec_type": spec_type,
        "status": status,
        "working_group": working_group,
        "series": series,
        "latest_version": latest_version,
        "specfile": spec_files,
        "versions": versions,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_threegpp_metadata(
    spec_number: str,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> dict[str, object]:
    """Fetch spec metadata from the 3GPP portal via dynareport redirect.

    1. Fetches ``https://www.3gpp.org/dynareport/{compact}.htm``
       which redirects to the portal specification details page.
    2. Parses the portal page HTML for:
       - General tab: title, status, type
       - Responsibility tab: primary working group
       - Versions tab: all version numbers with download filenames

    Args:
        spec_number: Spec number to fetch (e.g., "26.260").
        http_config: Optional HTTP configuration.
        http_cache_file: Optional explicit path to the HTTP cache database.

    Returns:
        Dictionary with keys:
          - spec_number: Normalized spec number
          - source_name: "3gpp"
          - source_identifier: Portal specification URL
          - metadata_payload: Dict with title, spec_type, status, working_group,
            series, latest_version, and specfile list
          - versions: List of version strings (e.g., ["19.1.0", "19.0.0", ...])

    Raises:
        SpecNotFoundError: If the spec is not found or has no versions.
    """
    normalized = normalize_spec_number(spec_number)
    compact = normalized.replace(".", "")
    dynareport_url = _DYNAREPORT_URL.format(compact=compact)

    session = create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    response = session.get(dynareport_url, timeout=30)
    response.raise_for_status()

    html_body = response.text or ""
    parsed = _parse_portal_html(html_body, normalized)

    if not parsed.get("has_versions"):
        _logger.warning(
            "Spec %s not found or no versions on portal (dynareport: %s)",
            normalized,
            dynareport_url,
        )
        raise SpecNotFoundError(
            f"Spec {normalized} not found on 3GPP portal or has no versions"
        )

    # Use the redirected URL as source identifier
    portal_url = str(response.url) if hasattr(response, "url") else dynareport_url

    return {
        "spec_number": normalized,
        "source_name": "3gpp",
        "source_identifier": portal_url,
        "metadata_payload": {
            "title": parsed["title"],
            "spec_type": parsed["spec_type"],
            "status": parsed["status"],
            "working_group": parsed["working_group"],
            "series": parsed["series"],
            "latest_version": parsed.get("latest_version"),
            "specfile": parsed.get("specfile", []),
        },
        "versions": parsed.get("versions", []),
    }
