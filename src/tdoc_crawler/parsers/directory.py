"""Directory HTML parsing utilities for TDoc discovery."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from tdoc_crawler.constants.patterns import EXCLUDED_DIRS_NORMALIZED, TDOC_SUBDIRS_NORMALIZED
from tdoc_crawler.logging import get_logger

logger = get_logger(__name__)


def parse_file_size(text_content: str) -> int | None:
    """Extract file size in bytes from text fragments.

    Args:
        text_content: Text containing file size (e.g., "123 KB", "4.5 MB")

    Returns:
        File size in bytes, or None if not found
    """
    size_match = re.search(r"(\d+)\s*([KMG]?)B", text_content, re.IGNORECASE)
    if not size_match:
        return None

    size_str = size_match.group(1)
    unit = size_match.group(2).upper()

    try:
        size = int(size_str)
    except ValueError:
        return None

    if unit == "K":
        size *= 1024
    elif unit == "M":
        size *= 1024 * 1024
    elif unit == "G":
        size *= 1024 * 1024 * 1024
    return size


def extract_subdirectories(base_url: str, html: str) -> list[str]:
    """Detect potential TDoc subdirectories (Docs/, Documents/, etc.).

    Args:
        base_url: Base URL of the directory listing
        html: HTML content of the directory page

    Returns:
        List of subdirectory URLs
    """
    soup = BeautifulSoup(html, "html.parser")
    subdirs: list[str] = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if not href or not isinstance(href, str):
            continue
        if href.startswith(("?", "..")):
            continue

        dir_name = href.rstrip("/").split("/")[-1]
        if dir_name.upper() not in TDOC_SUBDIRS_NORMALIZED:
            continue
        subdir_url = href if href.startswith("http") else urljoin(base_url, href)
        if not subdir_url.endswith("/"):
            subdir_url += "/"
        subdirs.append(subdir_url)
    return subdirs


def collect_tdocs_from_html(
    html: str,
    directory_url: str,
    meeting_id: int,
    meeting_short_name: str,
    pattern: re.Pattern[str],
    target_ids: set[str] | None,
    seen_ids: set[str],
) -> list[str]:
    """Parse a directory HTML listing for TDoc links.

    Args:
        html: HTML content of the directory page
        directory_url: URL of the directory being parsed
        meeting_id: Meeting identifier
        meeting_short_name: Short name of the meeting (e.g., "RAN1#98")
        pattern: Compiled regex pattern for matching TDoc IDs
        target_ids: Optional set of target TDoc IDs to filter
        seen_ids: Set tracking already-seen TDoc IDs (modified in place)

    Returns:
        List of JSON-serialized TDocMetadata records
    """
    soup = BeautifulSoup(html, "html.parser")
    serialized: list[str] = []

    for link in soup.find_all("a"):
        href_value = link.get("href")
        if not href_value or not isinstance(href_value, str):
            continue

        href = href_value.strip()
        if href in ("../", "./", "..", "."):
            continue
        if href.rstrip("/").split("/")[-1].upper() in EXCLUDED_DIRS_NORMALIZED:
            continue

        match = pattern.search(href)
        if not match:
            continue

        tdoc_id = match.group(1).upper()
        if tdoc_id in seen_ids:
            continue
        if target_ids is not None and tdoc_id not in target_ids:
            continue

        file_url = href if href.startswith(("http://", "https://")) else urljoin(directory_url, href)

        file_size = None
        parent = link.parent
        if parent:
            text_content = parent.get_text(" ")
            file_size = parse_file_size(text_content)

        now = datetime.now(UTC)
        payload = {
            "tdoc_id": tdoc_id,
            "meeting_id": meeting_id,
            "title": "Pending validation",
            "url": file_url,
            "source": "Unknown",
            "contact": "Unknown",
            "tdoc_type": "unknown",
            "for_purpose": "unknown",
            "agenda_item_nbr": "0.0",
            "agenda_item_text": "Unknown",
            "status": None,
            "meeting_name": meeting_short_name or None,
            "is_revision_of": None,
            "file_size": file_size,
            "date_created": None,
            "date_retrieved": now.isoformat().replace("+00:00", "Z"),
            "date_updated": now.isoformat().replace("+00:00", "Z"),
            "validated": False,
            "validation_failed": False,
        }
        serialized.append(json.dumps(payload))
        seen_ids.add(tdoc_id)

    return serialized


__all__ = [
    "collect_tdocs_from_html",
    "extract_subdirectories",
    "parse_file_size",
]
