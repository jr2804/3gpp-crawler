"""WhatTheSpec TDoc metadata source.

This module provides a TDocSource implementation that fetches metadata
from the whatthespec.net community API.
"""

from __future__ import annotations

from pathlib import Path

import requests

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.database.meetings import MeetingDatabase
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.models.base import HttpCacheConfig
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.base import TDocSource, TDocSourceConfig
from tdoc_crawler.utils.parse import parse_agenda_item_nbr

logger = get_logger(__name__)

WHATSPEC_BASE_URL = "https://whatthespec.net/3gpp/tdoc.php?name={tdoc}&api=1"


class WhatTheSpecResolutionError(Exception):
    """Raised when WhatTheSpec resolution fails."""


def resolve_via_whatthespec(
    tdoc_id: str,
    session: requests.Session | None = None,
    timeout: int = 30,
    http_cache: HttpCacheConfig | None = None,
    cache_manager_name: str | None = None,
) -> TDocMetadata | None:
    """Resolve TDoc metadata from whatthespec.net API.

    Args:
        tdoc_id: TDoc identifier (e.g., "S4-260001").
        session: Optional requests.Session to reuse.
        timeout: Request timeout in seconds.
        http_cache: HTTP cache configuration for hishel.
        cache_manager_name: Optional name of the cache manager to use for HTTP caching.

    Returns:
        TDocMetadata if found, otherwise None.
    """
    temp_session: requests.Session | None = None
    if session is None:
        temp_session = create_cached_session(cache_manager_name=cache_manager_name, http_cache=http_cache)
        active_session = temp_session
    else:
        active_session = session

    url = WHATSPEC_BASE_URL.format(tdoc=tdoc_id)
    try:
        response = active_session.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        error_msg = f"WhatTheSpec request failed for {tdoc_id}: {exc}"
        logger.error(error_msg)
        raise WhatTheSpecResolutionError(error_msg) from exc
    finally:
        if temp_session:
            temp_session.close()

    if not isinstance(payload, list) or not payload:
        return None

    record = payload[0] or {}
    resolved_id = str(record.get("name") or tdoc_id).strip().upper()
    meeting_raw = record.get("meeting")
    meeting_name = str(meeting_raw) if meeting_raw else ""
    agenda_item_nbr = parse_agenda_item_nbr(record.get("ainumber"))

    manager = resolve_cache_manager(cache_manager_name)
    with MeetingDatabase(manager.db_file) as db:
        meeting_id = db.resolve_meeting_id(meeting_name) or 0

    metadata = TDocMetadata(
        tdoc_id=resolved_id,
        meeting_id=meeting_id,
        title=str(record.get("title") or ""),
        url=str(record.get("link") or ""),
        source=str(record.get("source") or ""),
        contact=str(record.get("contact") or ""),
        tdoc_type=str(record.get("tdoctype") or "unknown"),
        for_purpose=str(record.get("for") or "unknown"),
        agenda_item_nbr=agenda_item_nbr,
        agenda_item_text=str(record.get("ainame") or "Unknown"),
        status=record.get("status"),
        is_revision_of=None,
        file_size=None,
        date_created=None,
        validated=False,
        validation_failed=False,
    )
    return metadata


class WhatTheSpecSource(TDocSource):
    """TDoc metadata source using whatthespec.net API.

    This source provides unauthenticated access to TDoc metadata through
    the WhatTheSpec community API. It's the preferred source for most users
    as it requires no credentials.
    """

    def __init__(
        self,
        config: TDocSourceConfig,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize WhatTheSpec source.

        Args:
            config: Source configuration
            session: Optional requests.Session to reuse
        """
        self.config = config
        self.session = session

    def fetch_by_id(
        self,
        tdoc_id: str,
        *,
        db_file: Path | None = None,
        timeout: int = 30,
    ) -> TDocMetadata | None:
        """Fetch TDoc metadata by TDoc ID from WhatTheSpec API.

        Args:
            tdoc_id: TDoc identifier (e.g., "S4-251364")
            db_file: Optional path to database for meeting resolution
            timeout: Request timeout in seconds

        Returns:
            TDocMetadata if found, None otherwise
        """
        try:
            metadata = resolve_via_whatthespec(
                tdoc_id=tdoc_id,
                http_cache=self.config.http_cache,
                timeout=timeout,
                session=self.session,
                cache_manager_name=self.config.cache_manager_name,
            )
            return metadata
        except Exception as exc:
            logger.debug(f"WhatTheSpec lookup failed for {tdoc_id}: {exc}")
            return None

    def fetch_by_meeting(
        self,
        meeting_id: int,
        *,
        timeout: int = 30,
    ) -> list[TDocMetadata]:
        """Fetch all TDoc metadata for a meeting.

        WhatTheSpec does not support bulk meeting queries, so this returns
        an empty list.

        Args:
            meeting_id: 3GPP meeting identifier
            timeout: Request timeout in seconds

        Returns:
            Empty list (not supported by this source)
        """
        raise NotImplementedError(f"WhatTheSpec does not support bulk meeting queries for meeting {meeting_id}")

    @property
    def source_name(self) -> str:
        """Return the name of this source for logging."""
        return "WhatTheSpec"

    @property
    def requires_authentication(self) -> bool:
        """Return whether this source requires authentication."""
        return False


__all__ = [
    "WHATSPEC_BASE_URL",
    "WhatTheSpecResolutionError",
    "WhatTheSpecSource",
    "resolve_via_whatthespec",
]
