"""TDoc crawler orchestrating parallel workers."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, as_completed
from dataclasses import dataclass

from pool_executors.pool_executors import create_executor
from tdoc_crawler.crawlers.parallel import fetch_meeting_tdocs
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import CrawlLimits, MeetingMetadata, MeetingQueryConfig, SortOrder, TDocCrawlConfig, TDocMetadata, WorkingGroup

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class TDocCrawlResult:
    """Summary of a TDoc crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


class TDocCrawler:
    """Configuration-driven crawler orchestrating subinterpreter workers."""

    def __init__(self, database: TDocDatabase) -> None:
        self.database = database

    def crawl(self, config: TDocCrawlConfig, progress_callback: Callable[[float, float], None] | None = None) -> TDocCrawlResult:
        """Execute a crawl using the provided configuration."""
        meetings = self._get_meetings_to_crawl(config)
        if not meetings:
            logger.warning("No meetings found matching criteria")
            return TDocCrawlResult(processed=0, inserted=0, updated=0, errors=["No meetings found"])

        meetings = self._apply_meeting_limits(meetings, config.limits)
        if not meetings:
            logger.warning("Meetings filtered out by limits configuration")
            return TDocCrawlResult(processed=0, inserted=0, updated=0, errors=["No meetings found after applying limits"])

        existing_ids: set[str] = set()
        if config.incremental:
            existing_ids = {tdoc_id.upper() for tdoc_id in self.database.get_existing_tdoc_ids(config.working_groups)}

        targets = set(config.target_ids) if config.target_ids else None

        collected: list[TDocMetadata] = []
        errors = asyncio.run(self._crawl_meetings_parallel(meetings, config, collected, existing_ids, targets))

        inserted = 0
        updated = 0
        if collected:
            inserted, updated = self.database.bulk_upsert_tdocs(collected, progress_callback=progress_callback)

        return TDocCrawlResult(
            processed=len(collected),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _apply_meeting_limits(self, meetings: list, limits: CrawlLimits) -> list:
        """Apply crawl limits to the meeting list."""
        limited = list(meetings)

        if limits.limit_meetings is not None and limits.limit_meetings != 0:
            limit = limits.limit_meetings
            limited = limited[:limit] if limit > 0 else limited[limit:]

        if limits.limit_meetings_per_wg is not None and limits.limit_meetings_per_wg != 0:
            per_wg_limit = abs(limits.limit_meetings_per_wg)
            per_wg_counts: dict[WorkingGroup, int] = {}
            filtered: list = []
            for meeting in limited:
                working_group = meeting.working_group
                count = per_wg_counts.get(working_group, 0)
                if count >= per_wg_limit:
                    continue
                per_wg_counts[working_group] = count + 1
                filtered.append(meeting)
            limited = filtered

        if limits.limit_wgs is not None and limits.limit_wgs != 0:
            max_groups = abs(limits.limit_wgs)
            seen_groups: set[WorkingGroup] = set()
            filtered: list = []
            for meeting in limited:
                working_group = meeting.working_group
                if working_group in seen_groups:
                    filtered.append(meeting)
                    continue
                if len(seen_groups) >= max_groups:
                    continue
                seen_groups.add(working_group)
                filtered.append(meeting)
            limited = filtered

        return limited

    def _get_meetings_to_crawl(self, config: TDocCrawlConfig) -> list:
        """Query meetings from the database based on configuration filters."""
        meeting_config = MeetingQueryConfig(
            cache_dir=config.cache_dir,
            working_groups=config.working_groups,
            subgroups=config.subgroups,
            limit=config.limits.limit_meetings,
            order=SortOrder.DESC,
            include_without_files=False,
        )

        meetings = self.database.query_meetings(meeting_config)

        if config.meeting_ids:
            meeting_id_set = set(config.meeting_ids)
            meetings = [meeting for meeting in meetings if meeting.meeting_id in meeting_id_set]

        if config.start_date:
            meetings = [meeting for meeting in meetings if meeting.start_date and meeting.start_date >= config.start_date]
        if config.end_date:
            meetings = [meeting for meeting in meetings if meeting.start_date and meeting.start_date <= config.end_date]

        return meetings

    def _filter_meetings_for_parallel_crawl(
        self,
        meetings: list,
        max_tdocs: int | None,
    ) -> list:
        """Filter meetings to respect max_tdocs limit via tdoc_count optimization.

        This method pre-filters meetings to skip those that would cause
        cumulative TDoc count to exceed max_tdocs. This prevents unnecessary
        subinterpreter task submission when limits will not be met.

        Args:
            meetings: List of meetings to filter
            max_tdocs: Maximum TDocs to crawl (None = no limit)

        Returns:
            Filtered list of meetings respecting tdoc_count optimization
        """
        if max_tdocs is None:
            return [m for m in meetings if m.files_url]

        filtered: list = []
        cumulative_tdocs = 0

        for meeting in meetings:
            if not meeting.files_url:
                continue

            meeting_tdocs = meeting.tdoc_count or 0
            if cumulative_tdocs + meeting_tdocs >= max_tdocs:
                continue

            filtered.append(meeting)
            cumulative_tdocs += meeting_tdocs

        return filtered

    def _crawl_meetings_parallel(
        self,
        meetings: list,
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> list[str]:
        """Launch subinterpreter workers to crawl meetings in parallel."""
        errors: list[str] = []
        seen_ids: set[str] = set()
        max_tdocs = None
        if config.limits.limit_tdocs is not None and config.limits.limit_tdocs != 0:
            max_tdocs = abs(config.limits.limit_tdocs)

        # Pre-filter meetings to optimize task submission
        meetings = self._filter_meetings_for_parallel_crawl(meetings, max_tdocs)

        target_tuple = tuple(targets) if targets else None

        # Select executor based on worker count
        if config.workers == 1:
            executor = create_executor("serial")
            executor_type = "serial"
        else:
            # Auto-selects InterpreterPoolExecutor (Python 3.14+) or ProcessPoolExecutor (fallback)
            executor = create_executor("subinterpreter", max_workers=config.workers)
            executor_type = "subinterpreter/process"

        logger.debug("Using %s executor with %d worker(s)", executor_type, config.workers)

        # Track start time for overall timeout enforcement
        start_time = time.monotonic()

        with executor:
            futures: dict[Future[tuple[str, ...]], MeetingMetadata] = {}

            for meeting in meetings:
                base_url = meeting.files_url.rstrip("/") + "/"
                future = executor.submit(
                    fetch_meeting_tdocs,
                    meeting.meeting_id,
                    base_url,
                    meeting.short_name or "",
                    config.timeout,
                    config.max_retries,
                    target_tuple,
                    str(config.cache_dir),
                    config.http_cache.ttl,
                    config.http_cache.refresh_ttl_on_access,
                )
                futures[future] = meeting

            # Process results as they complete
            for future in as_completed(futures):
                meeting = futures[future]
                try:
                    payloads = future.result()
                except Exception as exc:  # pragma: no cover - defensive, depends on network
                    short_name = meeting.short_name or str(meeting.meeting_id)
                    message = f"Meeting {short_name}: {exc}"
                    logger.warning(message)
                    errors.append(message)
                    continue

                limit_reached = self._process_payloads(
                    payloads,
                    collected,
                    seen_ids,
                    existing_ids,
                    config.incremental,
                    targets,
                    max_tdocs,
                )

                # Check if overall timeout exceeded
                elapsed = time.monotonic() - start_time
                timeout_exceeded = config.overall_timeout is not None and elapsed >= config.overall_timeout

                if limit_reached or (targets is not None and not targets) or timeout_exceeded:
                    # Cancel remaining futures
                    for pending_future in futures:
                        if not pending_future.done():
                            pending_future.cancel()
                    if timeout_exceeded:
                        message = f"Overall timeout of {config.overall_timeout}s exceeded after {elapsed:.1f}s"
                        logger.warning(message)
                        errors.append(message)
                    break

        return errors

    def _process_payloads(
        self,
        payloads: tuple[str, ...],
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        incremental: bool,
        targets: set[str] | None,
        max_tdocs: int | None,
    ) -> bool:
        """Convert worker payloads into TDocMetadata and apply filters.

        Returns True when a crawl limit (target IDs or limit_tdocs) has been
        reached and processing should stop.
        """
        for json_payload in payloads:
            metadata = TDocMetadata.model_validate_json(json_payload)
            tdoc_id = metadata.tdoc_id

            if tdoc_id in seen_ids:
                continue
            if incremental and tdoc_id in existing_ids:
                continue

            collected.append(metadata)
            seen_ids.add(tdoc_id)

            if targets is not None:
                targets.discard(tdoc_id)
                if not targets:
                    return True

            if max_tdocs is not None and len(collected) >= max_tdocs:
                return True

        return False


__all__ = [
    "TDocCrawlResult",
    "TDocCrawler",
]
