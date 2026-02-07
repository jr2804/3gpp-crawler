"""Resolve TDoc metadata via whatthespec.net API."""

from __future__ import annotations

import logging
from pathlib import Path

from decimal import Decimal, InvalidOperation

import requests

from tdoc_crawler.database import resolve_meeting_id, TDocDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.models.base import HttpCacheConfig
from tdoc_crawler.models.tdocs import TDocMetadata

logger = logging.getLogger(__name__)

WHATSPEC_BASE_URL = "https://whatthespec.net/3gpp/tdoc.php?name={tdoc}&api=1"


class WhatTheSpecResolutionError(Exception):
    """Raised when WhatTheSpec resolution fails."""


def _parse_agenda_item_nbr(value: object) -> Decimal:
    """Parse agenda item number as Decimal with fallback to zero."""
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        logger.warning(f"Invalid agenda item number '{value}': {exc}")
        return Decimal(0)


def _resolve_meeting_id(cache_dir: Path, meeting_name: str | None) -> int:
    """Resolve meeting name to meeting_id using local database."""
    if not meeting_name:
        return 0
    try:
        db_path = database_path(cache_dir)
        with TDocDatabase(db_path) as database:
            resolved = resolve_meeting_id(database, meeting_name)
    except Exception as exc:
        logger.warning(f"Failed to resolve meeting '{meeting_name}': {exc}")
        return 0
    return resolved or 0


def resolve_via_whatthespec(
    tdoc_id: str,
    cache_dir: Path,
    http_cache: HttpCacheConfig,
    timeout: int = 30,
) -> TDocMetadata | None:
    """Resolve TDoc metadata from whatthespec.net API.

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-260001").
        cache_dir: Directory for HTTP cache storage.
        http_cache: HTTP cache configuration for hishel.
        timeout: Request timeout in seconds.

    Returns:
        TDocMetadata if found, otherwise None.

    Raises:
        WhatTheSpecResolutionError: On network or timeout errors.

    Example:
        >>> from pathlib import Path
        >>> from tdoc_crawler.models.base import HttpCacheConfig
        >>> resolve_via_whatthespec("S4-260001", Path(".cache"), HttpCacheConfig())
    """
    session = create_cached_session(
        cache_dir=cache_dir,
        ttl=http_cache.ttl,
        refresh_ttl_on_access=http_cache.refresh_ttl_on_access,
        max_retries=3,
    )
    url = WHATSPEC_BASE_URL.format(tdoc=tdoc_id)
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        error_msg = f"WhatTheSpec request failed for {tdoc_id}: {exc}"
        logger.error(error_msg)
        raise WhatTheSpecResolutionError(error_msg) from exc
    finally:
        session.close()

    if not isinstance(payload, list) or not payload:
        return None

    record = payload[0] or {}
    resolved_id = str(record.get("name") or tdoc_id).strip().upper()
    meeting_name = record.get("meeting")
    agenda_item_nbr = _parse_agenda_item_nbr(record.get("ainumber"))

    metadata = TDocMetadata(
        tdoc_id=resolved_id,
        meeting_id=_resolve_meeting_id(cache_dir, meeting_name),
        meeting_name=meeting_name,
        title=str(record.get("title") or ""),
        url=str(record.get("link") or ""),
        source=str(record.get("source") or ""),
        contact=str(record.get("contact") or ""),
        tdoc_type=str(record.get("tdoctype") or "unknown"),
        for_purpose=str(record.get("for") or "unknown"),
        agenda_item_nbr=agenda_item_nbr,
        agenda_item_text=str(record.get("ainame") or "Unknown"),
        status=record.get("status"),
        validated=False,
        validation_failed=False,
    )
    return metadata


__all__ = ["WHATSPEC_BASE_URL", "WhatTheSpecResolutionError", "resolve_via_whatthespec"]
