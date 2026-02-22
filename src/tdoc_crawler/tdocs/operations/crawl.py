"""TDoc crawlers orchestrating parallel workers."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import Future, as_completed
from dataclasses import dataclass

from pool_executors.pool_executors import create_executor
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingMetadata, MeetingQueryConfig
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.models.crawl_limits import CrawlLimits
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocMetadata
from tdoc_crawler.workers.tdoc_worker import fetch_meeting_document_list_subinterpreter

logger = get_logger(__name__)


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
        if not isinstance(database, TDocDatabase):
            raise TypeError(f"Expected TDocDatabase, got {type(database)}")
        self.database = database

    def crawl(self, config: TDocCrawlConfig, progress_callback: Callable[[float, float], None] | None = None) -> TDocCrawlResult:
        """Execute a crawl using the provided configuration.

        Args:
            config: Configuration for the TDoc crawl
            progress_callback: Optional callback for progress updates

        Returns:
            Summary of crawl results
        """
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
        errors = self._crawl_meetings(meetings, config, collected, existing_ids, targets)

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

    def _get_meetings_to_crawl(self, config: TDocCrawlConfig) -> list:
        """Query meetings from the database based on configuration filters."""
        meeting_config = MeetingQueryConfig(
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

    def _crawl_meetings(
        self,
        meetings: list,
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> list[str]:
        """Launch subinterpreter workers to crawl meetings via document lists."""
        errors: list[str] = []
        seen_ids: set[str] = set()
        max_tdocs = None
        if config.limits.limit_tdocs is not None and config.limits.limit_tdocs != 0:
            max_tdocs = abs(config.limits.limit_tdocs)

        if targets is not None:
            targets = {item.upper() for item in targets}

        if config.workers == 1:
            executor = create_executor("serial")
            executor_type = "serial"
        else:
            executor = create_executor("multiprocessing", max_workers=config.workers)
            executor_type = "multiprocessing"

        logger.debug("Using %s executor with %d worker(s)", executor_type, config.workers)

        start_time = time.monotonic()

        with executor:
            futures: dict[Future[str], MeetingMetadata] = {}

            for meeting in meetings:
                future = executor.submit(
                    fetch_meeting_document_list_subinterpreter,
                    meeting_id=meeting.meeting_id,
                    timeout=config.timeout,
                    http_cache=config.http_cache,
                    cache_manager_name=config.cache_manager_name,
                )
                futures[future] = meeting

            for future in as_completed(futures):
                meeting = futures[future]
                try:
                    json_payload = future.result()
                except Exception as exc:  # pragma: no cover - defensive, depends on network
                    short_name = meeting.short_name or str(meeting.meeting_id)
                    message = f"Meeting {short_name}: {exc}"
                    logger.warning(message)
                    errors.append(message)
                    continue

                limit_reached = self._process_document_list_response(
                    json_payload,
                    meeting,
                    collected,
                    seen_ids,
                    existing_ids,
                    config.incremental,
                    targets,
                    max_tdocs,
                    errors,
                )

                elapsed = time.monotonic() - start_time
                timeout_exceeded = config.overall_timeout is not None and elapsed >= config.overall_timeout

                if limit_reached or (targets is not None and not targets) or timeout_exceeded:
                    for pending_future in futures:
                        if not pending_future.done():
                            pending_future.cancel()
                    if timeout_exceeded:
                        message = f"Overall timeout of {config.overall_timeout}s exceeded after {elapsed:.1f}s"
                        logger.warning(message)
                        errors.append(message)
                    break

        return errors

    @staticmethod
    def _apply_meeting_limits(meetings: list, limits: CrawlLimits) -> list:
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

    @staticmethod
    def _process_document_list_response(
        json_payload: str,
        meeting: MeetingMetadata,
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        incremental: bool,
        targets: set[str] | None,
        max_tdocs: int | None,
        errors: list[str],
    ) -> bool:
        """Convert document list payload into TDocMetadata and apply filters.

        Returns True when a crawl limit (target IDs or limit_tdocs) has been
        reached and processing should stop.
        """
        try:
            response_data = json.loads(json_payload)
        except json.JSONDecodeError as exc:
            short_name = meeting.short_name or str(meeting.meeting_id)
            message = f"Failed to parse document list response for meeting {short_name}: {exc}"
            logger.warning(message)
            errors.append(message)
            return False

        if isinstance(response_data, dict) and "_error" in response_data:
            error_info = response_data["_error"]
            short_name = meeting.short_name or str(meeting.meeting_id)
            message = f"Document list method failed for meeting {short_name}: {error_info.get('error', 'Unknown error')}"
            logger.warning(message)
            errors.append(message)
            return False

        if not isinstance(response_data, list):
            short_name = meeting.short_name or str(meeting.meeting_id)
            message = f"Unexpected document list response for meeting {short_name}"
            logger.warning(message)
            errors.append(message)
            return False

        for tdoc_json in response_data:
            metadata = TDocMetadata.model_validate_json(tdoc_json)
            tdoc_id = metadata.tdoc_id

            if tdoc_id in seen_ids:
                continue
            if incremental and tdoc_id in existing_ids:
                continue
            if targets is not None and tdoc_id not in targets:
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
