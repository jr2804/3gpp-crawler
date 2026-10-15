"""TDoc fetching operations using source abstraction.

This module provides unified fetching interface that uses the TDocSource
abstraction to fetch metadata from various sources (WhatTheSpec, Portal, etc.).
"""

from __future__ import annotations

import types
import typing
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import niquests as requests
from pydantic import ValidationError

from tdoc_crawler.config.settings import HttpConfig, PathConfig
from tdoc_crawler.credentials import resolve_credentials
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.logging import get_logger
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.tdocs.sources import (
    DocumentListSource,
    PortalSource,
    TDocSourceConfig,
    WhatTheSpecSource,
)
from tdoc_crawler.utils.misc import utc_now

logger = get_logger(__name__)


# Names of fields WhatTheSpec cannot supply, derived from ``TDocMetadata``
# itself by type: db_pk, datetime, and bool audit fields are all server-side
# facts that come from the local crawler, not WhatTheSpec. Adding a new field
# of one of those types makes it unrefreshable automatically — no edit here
# needed.
_UNREFRESHABLE_FIELD_TYPES: tuple[type, ...] = (datetime, bool)


class FetchMethod(Enum):
    """Enumeration of available TDoc fetching methods."""

    PORTAL_URL_ONLY = "portal_url_only"
    PORTAL_FULL_METADATA = "portal_full_metadata"
    WHATTHESPEC = "whatthespec"
    DOCUMENT_LIST = "document_list"


@dataclass(frozen=True, slots=True)
class _RefreshableField:
    """A TDoc field WhatTheSpec can supply, with rules for when to overwrite.

    Attributes:
        field_name: Attribute name on ``TDocMetadata``.
        is_empty_on_orphan: Predicate that returns True when the orphan's
            current value is a default/placeholder that should be replaced.
        is_meaningful_on_fresh: Predicate that returns True when the
            WhatTheSpec-returned value is worth applying (non-empty, not a
            known placeholder).
    """

    field_name: str
    is_empty_on_orphan: Callable[[TDocMetadata], bool]
    is_meaningful_on_fresh: Callable[[object], bool]


class FetchMissingResult:
    """Result from fetch_missing_tdocs orchestration."""

    def __init__(
        self,
        refreshed: list[TDocMetadata],
        fetch_result: TDocCrawlResult | None = None,
        used_whatthespec_fallback: bool = False,
    ) -> None:
        """Initialize fetch result.

        Args:
            refreshed: Updated list of TDoc metadata after fetching
            fetch_result: Result of the batch fetch operation
            used_whatthespec_fallback: Whether WhatTheSpec was used as fallback
        """
        self.refreshed = refreshed
        self.fetch_result = fetch_result
        self.used_whatthespec_fallback = used_whatthespec_fallback


def is_orphan_tdoc(record: TDocMetadata) -> bool:
    """A TDoc is orphaned when both ``meeting_id`` and ``tbid`` are unset.

    Orphans arise when a doc is fetched via WhatTheSpec (whose ``meeting``
    field is the FTP directory name, not a local meeting identifier — see
    memory #425) and the underlying meeting isn't local, so neither
    ``resolve_meeting_id`` nor ``_resolve_tbid`` can fill in the linkage.
    Orphan records are valid but their meeting/tbid is unrecoverable from
    the local DB alone.
    """
    return record.meeting_id == 0 and record.tbid == 0


def _build_orphan_refreshable_fields() -> tuple[_RefreshableField, ...]:
    """Derive refreshable fields from ``TDocMetadata.model_fields``.

    A field is refreshable iff:

    * It has no non-trivial default factory (so we can detect "still at
      default"); ``date_retrieved`` etc. have ``default_factory=utc_now`` and
      are excluded automatically by ``_UNREFRESHABLE_FIELD_TYPES``.
    * It is **not** unrefreshable (computed from the model by type — db_pk,
      datetime, and bool audit fields are all server-side facts).

    The orphan's "is empty" check compares against the model's declared
    default — placeholder strings (``"unknown"``, ``"Unknown"``, …) come
    from the single source of truth on the model, not duplicated here.
    """
    unrefreshable = _build_unrefreshable_fields()
    fields: list[_RefreshableField] = []
    for field_name, pydantic_field in TDocMetadata.model_fields.items():
        if field_name in unrefreshable:
            continue
        if pydantic_field.default_factory is not None:
            # Field has a non-trivial default (e.g. ``utc_now``); we can't
            # statically detect "still at default", so skip it.
            continue
        # ``pydantic_field.default`` is the sentinel we compare against.
        # For ``status: str | None = None`` it's ``None`` — meaning the field
        # is "empty" iff it's currently ``None``. That's correct.
        sentinel: object = pydantic_field.default

        def _is_empty(
            record: TDocMetadata,
            _sentinel: object = sentinel,
            _name: str = field_name,
        ) -> bool:
            return getattr(record, _name, None) == _sentinel

        fields.append(
            _RefreshableField(
                field_name=field_name,
                is_empty_on_orphan=_is_empty,
                is_meaningful_on_fresh=_is_meaningful,
            ),
        )
    return tuple(fields)


def _is_meaningful(value: object) -> bool:
    """Reject ``None`` and empty strings."""
    if value is None:
        return False
    return not (isinstance(value, str) and not value)


def _build_unrefreshable_fields() -> frozenset[str]:
    """Compute fields WhatTheSpec can't supply from ``TDocMetadata`` model.

    Excludes: the primary key, anything typed as ``datetime`` or ``bool``
    (server-side audit/timestamp fields), and ``meeting_id``/``tbid`` whose
    linkage is structurally unrecoverable (see ``is_orphan_tdoc``).
    """
    excluded: set[str] = set()
    for field_name, pydantic_field in TDocMetadata.model_fields.items():
        if getattr(pydantic_field, "db_pk", False):
            excluded.add(field_name)
            continue
        annotation = pydantic_field.annotation
        if annotation is None:
            continue
        # Unwrap Optional[X] / Union[X, None] — only the non-None type matters.
        non_none_types = set(_non_none_types(annotation))
        if non_none_types & set(_UNREFRESHABLE_FIELD_TYPES):
            excluded.add(field_name)
    excluded.update({"meeting_id", "tbid"})
    return frozenset(excluded)


def _non_none_types(annotation: object) -> tuple[type, ...]:
    """Return the non-``None`` types from an ``Optional``/``Union`` annotation.

    ``str | None`` → ``(str,)``. ``Optional[datetime]`` → ``(datetime,)``.
    Plain ``str`` → ``(str,)``.
    """
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return tuple(t for t in typing.get_args(annotation) if t is not type(None))
    if isinstance(annotation, type):
        return (annotation,)
    return ()


_ORPHAN_REFRESHABLE_FIELDS: tuple[_RefreshableField, ...] = _build_orphan_refreshable_fields()


async def refresh_orphan_metadata(
    database: TDocDatabase,
    orphan: TDocMetadata,
    *,
    session: requests.Session | None = None,
    http_cache_file: Path | None = None,
) -> TDocMetadata:
    """Refresh an orphan TDoc's metadata from WhatTheSpec.

    Updates only fields whose orphan value is a default/placeholder AND whose
    WhatTheSpec-returned value is meaningful. Skips fields WhatTheSpec can't
    provide (notably ``meeting_id`` and ``tbid``) so the orphan stays orphan
    — the linkage is structurally unrecoverable without the local meeting
    record. Refresh rules live in ``_ORPHAN_REFRESHABLE_FIELDS``; add new
    fields there rather than hard-coding here.

    Returns the (possibly mutated and re-persisted) record.
    """
    del database  # currently unused — kept for parity with other fetch helpers
    config = TDocSourceConfig(
        http_config=None,
        http_cache_file=http_cache_file,
    )
    source = WhatTheSpecSource(config=config, session=session)
    try:
        fresh = source.fetch_by_id(orphan.tdoc_id)
    except Exception as exc:
        logger.warning("WhatTheSpec refresh failed for orphan %s: %s", orphan.tdoc_id, exc)
        return orphan
    if fresh is None:
        logger.warning("WhatTheSpec returned no data for orphan %s", orphan.tdoc_id)
        return orphan

    updates: dict[str, object] = {}
    for field in _ORPHAN_REFRESHABLE_FIELDS:
        if not field.is_empty_on_orphan(orphan):
            continue
        new_value = getattr(fresh, field.field_name, None)
        if not field.is_meaningful_on_fresh(new_value):
            continue
        updates[field.field_name] = new_value

    if not updates:
        return orphan

    updates["date_updated"] = utc_now()
    refreshed = TDocDatabase._clone_tdoc(orphan, updates)
    await refreshed.save()
    logger.info("Refreshed orphan %s with %d fields from WhatTheSpec", orphan.tdoc_id, len(updates))
    return refreshed


def create_source(
    method: FetchMethod,
    config: TDocSourceConfig,
    session: requests.Session | None = None,
) -> WhatTheSpecSource | PortalSource | DocumentListSource:
    """Create TDoc source based on fetch method.

    Args:
        method: Fetch method to use
        config: Source configuration
        session: Optional requests.Session to reuse

    Returns:
        Configured TDoc source instance

    Raises:
        ValueError: If method requires credentials but none provided
    """
    if method == FetchMethod.WHATTHESPEC:
        return WhatTheSpecSource(config=config, session=session)
    if method == FetchMethod.PORTAL_FULL_METADATA:
        return PortalSource(config=config)
    if method == FetchMethod.DOCUMENT_LIST:
        return DocumentListSource(config=config)
    if method == FetchMethod.PORTAL_URL_ONLY:
        # For URL-only method, we'll handle it separately as it doesn't fit the source pattern
        msg = "PORTAL_URL_ONLY method should be handled separately"
        raise ValueError(msg)
    msg = f"Unknown fetch method: {method}"
    raise ValueError(msg)


async def fetch_missing_tdocs(
    database: TDocDatabase,
    config: TDocQueryConfig,
    results: list[TDocMetadata],
    full_metadata: bool = False,
    use_whatthespec: bool = False,
    session: requests.Session | None = None,
    http_cache_file: Path | None = None,
    db_file: Path | None = None,
) -> FetchMissingResult:
    """Fetch missing TDocs if any are requested but not found in database.

    Orchestrates fetching based on flags, uses WhatTheSpec fallback when needed.

    Args:
        database: Database instance
        config: TDocQueryConfig with requested TDoc IDs
        results: Current query results
        full_metadata: If True, fetch full metadata from portal
        use_whatthespec: If True, always use WhatTheSpec
        session: Optional requests.Session to reuse
        http_cache_file: Optional path to HTTP cache database file
        db_file: Optional path to metadata database file

    Returns:
        FetchMissingResult with updated results and fetch statistics
    """
    if not config.tdoc_ids:
        return FetchMissingResult(refreshed=results)

    requested = [value.upper() for value in config.tdoc_ids]
    found = {item.tdoc_id for item in results}
    missing = [value for value in requested if value not in found]
    if not missing:
        return FetchMissingResult(refreshed=results)

    # Log what we're about to do
    if use_whatthespec:
        logger.info(f"Fetching missing TDocs via WhatTheSpec: {', '.join(missing)}")
    elif full_metadata:
        logger.info(f"Fetching missing TDocs with full metadata: {', '.join(missing)}")
    else:
        logger.info(f"Fetching missing TDocs: {', '.join(missing)}")

    # Handle use_whatthespec flag - always use WhatTheSpec method
    if use_whatthespec:
        fetch_result = await fetch_via_whatthespec_batch(database, missing, session=session, http_cache_file=http_cache_file, db_file=db_file)
        refreshed = await database.query_tdocs(config)
        return FetchMissingResult(
            refreshed=refreshed,
            fetch_result=fetch_result,
            used_whatthespec_fallback=True,
        )

    # Handle full_metadata flag - use authenticated portal method
    credentials = resolve_credentials(None, None)
    credentials_unavailable = credentials is None

    if full_metadata:
        if credentials_unavailable:
            fetch_result = TDocCrawlResult(
                processed=len(missing),
                inserted=0,
                updated=0,
                errors=["Portal credentials required for full metadata fetching"],
            )
            logger.warning("Portal credentials required for full metadata fetching")
            return FetchMissingResult(refreshed=results, fetch_result=fetch_result)

        fetch_result = await fetch_missing_tdocs_batch(
            database=database,
            missing_ids=missing,
            session=session,
            http_cache_file=http_cache_file,
        )

        refreshed = await database.query_tdocs(config)
        return FetchMissingResult(refreshed=refreshed, fetch_result=fetch_result)

    # Default behavior - use unauthenticated portal method with WhatTheSpec fallback
    fetch_result = await fetch_missing_tdocs_batch(
        database=database,
        missing_ids=missing,
        session=session,
        http_cache_file=http_cache_file,
    )

    # Check if we should try whatthespec fallback
    has_credentials_error = any("credentials required" in str(err).lower() for err in fetch_result.errors)
    if credentials_unavailable or has_credentials_error:
        logger.info("Falling back to WhatTheSpec for missing TDocs due to credential issues")
        fetch_result = await fetch_via_whatthespec_batch(database, missing, session=session, http_cache_file=http_cache_file, db_file=db_file)
        used_fallback = True
    else:
        used_fallback = False

    refreshed = await database.query_tdocs(config)
    return FetchMissingResult(
        refreshed=refreshed,
        fetch_result=fetch_result,
        used_whatthespec_fallback=used_fallback,
    )


async def fetch_missing_tdocs_batch(
    database: TDocDatabase,
    missing_ids: list[str],
    session: requests.Session | None = None,
    timeout: int = 30,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> TDocCrawlResult:
    """Fetch multiple missing TDocs using portal authentication.

    Args:
        database: Database instance for storing results
        missing_ids: List of TDoc IDs to fetch
        http_config: HTTP configuration from ThreeGPPConfig
        timeout: Request timeout in seconds
        session: Optional requests.Session to reuse
        http_cache_file: Optional path to HTTP cache database file

    Returns:
        TDocCrawlResult with fetch statistics
    """
    errors = []
    inserted_count = 0
    updated_count = 0

    # Create source configuration and portal source
    config = TDocSourceConfig(
        http_config=http_config,
        http_cache_file=http_cache_file,
        timeout=timeout,
    )
    source = PortalSource(config=config)

    for tdoc_id in missing_ids:
        try:
            metadata = source.fetch_by_id(tdoc_id, timeout=timeout)
            if metadata is None:
                error_msg = f"Portal returned no data for {tdoc_id}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            # meeting_id resolution is now done inside source modules

            inserted, updated = await database.upsert_tdoc(metadata)
            if inserted:
                inserted_count += 1
            elif updated:
                updated_count += 1

            logger.info("Successfully fetched and stored %s", tdoc_id)

        except ValidationError as exc:
            validation_errors = []
            for error in exc.errors():
                field = error["loc"][0] if error["loc"] else "unknown"
                message = error["msg"]
                validation_errors.append(f"{field}: {message}")

            error_msg = f"Failed to fetch {tdoc_id}: {'; '.join(validation_errors)}"
            logger.warning(error_msg)
            errors.append(error_msg)
        except Exception as exc:
            error_msg = f"Failed to fetch {tdoc_id}: {exc}"
            logger.exception(error_msg)
            errors.append(error_msg)

    # Clean up source
    source.close()

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


async def fetch_via_whatthespec_batch(
    database: TDocDatabase,
    missing_ids: list[str],
    http_config: HttpConfig | None = None,
    session: requests.Session | None = None,
    http_cache_file: Path | None = None,
    db_file: Path | None = None,
) -> TDocCrawlResult:
    """Fetch multiple missing TDocs using WhatTheSpec.net API.

    Args:
        database: Database instance for storing results
        missing_ids: List of TDoc IDs to fetch
        http_config: HTTP configuration from ThreeGPPConfig
        session: Optional requests.Session to reuse
        http_cache_file: Optional path to HTTP cache database file
        db_file: Optional path to metadata database file

    Returns:
        TDocCrawlResult with fetch statistics
    """
    errors = []
    inserted_count = 0
    updated_count = 0

    # Create source configuration and WhatTheSpec source
    config = TDocSourceConfig(
        http_config=http_config,
        http_cache_file=http_cache_file,
    )
    source = WhatTheSpecSource(config=config, session=session)
    resolved_db_file = db_file if db_file is not None else PathConfig().db_file

    for tdoc_id in missing_ids:
        try:
            metadata = source.fetch_by_id(tdoc_id, db_file=resolved_db_file)
            if metadata:
                inserted, updated = await database.upsert_tdoc(metadata)
                if inserted:
                    inserted_count += 1
                elif updated:
                    updated_count += 1
                logger.info("Successfully fetched %s via whatthespec", tdoc_id)
            else:
                error_msg = f"WhatTheSpec returned no data for {tdoc_id}"
                logger.warning(error_msg)
                errors.append(error_msg)
        except Exception as exc:
            error_msg = f"Error fetching {tdoc_id} via whatthespec: {exc}"
            logger.warning(error_msg)
            errors.append(error_msg)

    return TDocCrawlResult(
        processed=len(missing_ids),
        inserted=inserted_count,
        updated=updated_count,
        errors=errors,
    )


__all__ = [
    "FetchMethod",
    "FetchMissingResult",
    "create_source",
    "fetch_missing_tdocs",
    "fetch_missing_tdocs_batch",
    "fetch_via_whatthespec_batch",
]
