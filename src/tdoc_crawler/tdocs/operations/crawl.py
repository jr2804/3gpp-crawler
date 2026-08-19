"""TDoc crawlers orchestrating parallel workers."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import Executor, Future, as_completed
from dataclasses import dataclass
from datetime import date

from pool_executors import create_executor

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.logging import get_logger
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import SortOrder
from tdoc_crawler.tdocs.models import TDocCrawlConfig
from tdoc_crawler.utils.normalization import normalize_tdoc_id
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
            msg = f"Expected TDocDatabase, got {type(database)}"
            raise TypeError(msg)
        self.database = database

    async def crawl(self, config: TDocCrawlConfig, progress_callback: Callable[[float, float], None] | None = None) -> TDocCrawlResult:
        """Execute a crawl using the provided configuration.

        Args:
            config: Configuration for the TDoc crawl
            progress_callback: Optional callback for progress updates

        Returns:
            Summary of crawl results
        """
        meetings = await self._get_meetings_to_crawl(config)
        if not meetings:
            logger.warning("No meetings found matching criteria")
            return TDocCrawlResult(processed=0, inserted=0, updated=0, errors=["No meetings found"])

        meetings = self._apply_meeting_limits(
            meetings,
            config.limit_meetings,
            config.limit_meetings_per_subwg,
            config.limit_subwgs,
        )
        if not meetings:
            logger.warning("Meetings filtered out by limits configuration")
            return TDocCrawlResult(processed=0, inserted=0, updated=0, errors=["No meetings found after applying limits"])

        existing_ids: set[str] = set()
        if config.incremental:
            existing_ids = {tdoc_id.upper() for tdoc_id in await self.database.get_existing_tdoc_ids(config.working_groups)}

        targets = set(config.target_ids) if config.target_ids else None

        collected: list[TDocMetadata] = []
        errors = self._crawl_meetings(meetings, config, collected, existing_ids, targets)

        inserted = 0
        updated = 0
        if collected:
            inserted, updated = await self.database.bulk_upsert_tdocs(collected, progress_callback=progress_callback)

        return TDocCrawlResult(
            processed=len(collected),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    async def _get_meetings_to_crawl(self, config: TDocCrawlConfig) -> list[MeetingMetadata]:
        """Query meetings from the database based on configuration filters."""
        meeting_config = MeetingQueryConfig(
            working_groups=config.working_groups,
            subgroups=config.subgroups,
            limit=config.limit_meetings,
            order=SortOrder.DESC,
            include_without_files=False,
        )

        meetings = await self.database.query_meetings(meeting_config)

        filtered = self._filter_meetings_by_ids(meetings, config.meeting_ids)
        filtered = self._filter_meetings_by_start_date(filtered, config.start_date)
        return self._filter_meetings_by_end_date(filtered, config.end_date)

    def _crawl_meetings(
        self,
        meetings: list[MeetingMetadata],
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> list[str]:
        """Launch subinterpreter workers to crawl meetings via document lists."""
        errors: list[str] = []
        seen_ids: set[str] = set()
        max_tdocs = self._resolve_max_tdocs(config.limit_tdocs)
        targets = self._normalize_targets(targets)

        executor, executor_type = self._create_executor_for_workers(config.workers, config.executor)

        logger.debug("Using %s executor with %d worker(s)", executor_type, config.workers)

        start_time = time.monotonic()

        with executor:
            futures = self._submit_meeting_futures(executor, meetings, config)

            for future in as_completed(futures):
                meeting = futures[future]
                json_payload = self._handle_future_error(future, meeting, errors)
                if json_payload is None:
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

                timeout_exceeded, elapsed = self._timeout_exceeded(config.overall_timeout, start_time)
                if self._should_stop_processing(limit_reached, targets, timeout_exceeded):
                    self._cancel_pending_futures(futures)
                    self._append_timeout_error_if_needed(timeout_exceeded, config.overall_timeout, elapsed, errors)
                    break

        return errors

    @classmethod
    def _apply_meeting_limits(
        cls,
        meetings: list[MeetingMetadata],
        limit_meetings: int | None,
        limit_meetings_per_subwg: int | None,
        limit_subwgs: int | None,
    ) -> list[MeetingMetadata]:
        """Apply crawl limits to the meeting list."""
        limited = list(meetings)
        limited = cls._apply_total_meeting_limit(limited, limit_meetings)
        limited = cls._apply_meetings_per_subwg_limit(limited, limit_meetings_per_subwg)
        return cls._apply_subworking_group_limit(limited, limit_subwgs)

    @classmethod
    def _parse_document_list_payload(cls, json_payload: str, meeting: MeetingMetadata, errors: list[str]) -> list[str] | None:
        """Decode worker payload and validate expected list shape."""
        short_name = cls._meeting_short_name(meeting)
        try:
            response_data = json.loads(json_payload)
        except json.JSONDecodeError as exc:
            message = f"Failed to parse document list response for meeting {short_name}: {exc}"
            logger.warning(message)
            errors.append(message)
            return None

        if isinstance(response_data, dict) and "_error" in response_data:
            error_info = response_data["_error"]
            message = f"Document list method failed for meeting {short_name}: {error_info.get('error', 'Unknown error')}"
            logger.warning(message)
            errors.append(message)
            return None

        if not isinstance(response_data, list):
            message = f"Unexpected document list response for meeting {short_name}"
            logger.warning(message)
            errors.append(message)
            return None

        return response_data

    @staticmethod
    def _filter_meetings_by_ids(meetings: list[MeetingMetadata], meeting_ids: list[int] | None) -> list[MeetingMetadata]:
        """Filter meetings by explicit meeting ID allowlist."""
        if not meeting_ids:
            return meetings
        meeting_id_set = set(meeting_ids)
        return [meeting for meeting in meetings if meeting.meeting_id in meeting_id_set]

    @staticmethod
    def _filter_meetings_by_start_date(
        meetings: list[MeetingMetadata],
        start_date: date | None,
    ) -> list[MeetingMetadata]:
        """Filter meetings with start date greater than or equal to provided date."""
        if not start_date:
            return meetings
        return [meeting for meeting in meetings if meeting.start_date and meeting.start_date >= start_date]

    @staticmethod
    def _filter_meetings_by_end_date(
        meetings: list[MeetingMetadata],
        end_date: date | None,
    ) -> list[MeetingMetadata]:
        """Filter meetings with start date less than or equal to provided date."""
        if not end_date:
            return meetings
        return [meeting for meeting in meetings if meeting.start_date and meeting.start_date <= end_date]

    @staticmethod
    def _resolve_max_tdocs(limit_tdocs: int | None) -> int | None:
        """Normalize limit_tdocs into an absolute positive cap when set."""
        if limit_tdocs is None or limit_tdocs == 0:
            return None
        return abs(limit_tdocs)

    @staticmethod
    def _normalize_targets(targets: set[str] | None) -> set[str] | None:
        """Uppercase target IDs for case-insensitive matching."""
        if targets is None:
            return None
        return {normalize_tdoc_id(item) for item in targets}

    @staticmethod
    def _create_executor_for_workers(workers: int, executor: str | None = None) -> tuple[Executor, str]:
        """Create configured executor and return it with a label for logging.

        Args:
            workers: Number of parallel workers.
            executor: Optional executor type override ('serial', 'threading',
                'multiprocessing', 'subinterpreter'). None = auto: serial when
                workers=1, else multiprocessing.
        """
        if executor:
            executor = executor.lower()
        if executor == "serial" or (executor is None and workers == 1):
            return create_executor("serial"), "serial"
        if executor is not None:
            return create_executor(executor, max_workers=workers), executor
        return create_executor("multiprocessing", max_workers=workers), "multiprocessing"

    @staticmethod
    def _submit_meeting_futures(executor: Executor, meetings: list[MeetingMetadata], config: TDocCrawlConfig) -> dict[Future[str], MeetingMetadata]:
        """Submit worker tasks for each meeting and map futures back to meeting metadata."""
        futures: dict[Future[str], MeetingMetadata] = {}
        for meeting in meetings:
            future = executor.submit(
                fetch_meeting_document_list_subinterpreter,
                meeting_id=meeting.meeting_id,
                timeout=config.timeout,
                http_config=config.http_config,
                files_url=meeting.files_url,
            )
            futures[future] = meeting
        return futures

    @staticmethod
    def _cancel_pending_futures(futures: dict[Future[str], MeetingMetadata]) -> None:
        """Cancel any not-yet-started/unfinished futures."""
        for pending_future in futures:
            if not pending_future.done():
                pending_future.cancel()

    @staticmethod
    def _handle_future_error(future: Future[str], meeting: MeetingMetadata, errors: list[str]) -> str | None:
        """Resolve future payload or collect error and return None on failure."""
        try:
            return future.result()
        except Exception as exc:  # pragma: no cover - defensive, depends on network
            short_name = meeting.short_name or str(meeting.meeting_id)
            message = f"Meeting {short_name}: {exc}"
            logger.warning(message)
            errors.append(message)
            return None

    @staticmethod
    def _timeout_exceeded(overall_timeout: float | None, start_time: float) -> tuple[bool, float]:
        """Check elapsed crawl time against optional overall timeout."""
        elapsed = time.monotonic() - start_time
        if overall_timeout is None:
            return False, elapsed
        return elapsed >= overall_timeout, elapsed

    @staticmethod
    def _should_stop_processing(limit_reached: bool, targets: set[str] | None, timeout_exceeded: bool) -> bool:
        """Determine whether crawl loop should stop after current completion."""
        return limit_reached or (targets is not None and not targets) or timeout_exceeded

    @staticmethod
    def _append_timeout_error_if_needed(timeout_exceeded: bool, overall_timeout: float | None, elapsed: float, errors: list[str]) -> None:
        """Record timeout message when loop exits because overall timeout was reached."""
        if not timeout_exceeded or overall_timeout is None:
            return
        message = f"Overall timeout of {overall_timeout}s exceeded after {elapsed:.1f}s"
        logger.warning(message)
        errors.append(message)

    @staticmethod
    def _apply_total_meeting_limit(meetings: list[MeetingMetadata], limit: int | None) -> list[MeetingMetadata]:
        """Apply absolute meeting count limit across all meetings."""
        if limit is None or limit == 0:
            return meetings
        return meetings[:limit] if limit > 0 else meetings[limit:]

    @staticmethod
    def _apply_meetings_per_subwg_limit(meetings: list[MeetingMetadata], per_subwg_limit: int | None) -> list[MeetingMetadata]:
        """Limit number of meetings per sub-working group."""
        if per_subwg_limit is None or per_subwg_limit == 0:
            return meetings

        max_per_subwg = abs(per_subwg_limit)
        per_subwg_counts: dict[int, int] = {}
        filtered: list[MeetingMetadata] = []
        for meeting in meetings:
            wg_id = meeting.subtb or meeting.tbid
            count = per_subwg_counts.get(wg_id, 0)
            if count >= max_per_subwg:
                continue
            per_subwg_counts[wg_id] = count + 1
            filtered.append(meeting)
        return filtered

    @staticmethod
    def _apply_subworking_group_limit(meetings: list[MeetingMetadata], limit_subwgs: int | None) -> list[MeetingMetadata]:
        """Limit number of distinct sub-working groups represented in meetings."""
        if limit_subwgs is None or limit_subwgs == 0:
            return meetings

        max_groups = abs(limit_subwgs)
        seen_groups: set[int] = set()
        filtered: list[MeetingMetadata] = []
        for meeting in meetings:
            wg_id = meeting.subtb or meeting.tbid
            if wg_id in seen_groups:
                filtered.append(meeting)
                continue
            if len(seen_groups) >= max_groups:
                continue
            seen_groups.add(wg_id)
            filtered.append(meeting)
        return filtered

    @staticmethod
    def _meeting_short_name(meeting: MeetingMetadata) -> str:
        """Return a stable meeting label for log and error messages."""
        return meeting.short_name or str(meeting.meeting_id)

    @staticmethod
    def _should_include_tdoc(
        tdoc_id: str,
        seen_ids: set[str],
        existing_ids: set[str],
        incremental: bool,
        targets: set[str] | None,
    ) -> bool:
        """Apply deduplication, incremental and target filters for one TDoc."""
        if tdoc_id in seen_ids:
            return False
        if incremental and tdoc_id in existing_ids:
            return False
        return targets is None or tdoc_id in targets

    @staticmethod
    def _limit_reached(collected_count: int, max_tdocs: int | None) -> bool:
        """Check whether global TDoc collection limit has been reached."""
        return max_tdocs is not None and collected_count >= max_tdocs

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
        response_data = TDocCrawler._parse_document_list_payload(json_payload, meeting, errors)
        if response_data is None:
            return False

        for tdoc_json in response_data:
            metadata = TDocMetadata.model_validate_json(tdoc_json)
            tdoc_id = metadata.tdoc_id

            if not TDocCrawler._should_include_tdoc(tdoc_id, seen_ids, existing_ids, incremental, targets):
                continue

            collected.append(metadata)
            seen_ids.add(tdoc_id)

            if targets is not None:
                targets.discard(tdoc_id)
                if not targets:
                    return True

            if TDocCrawler._limit_reached(len(collected), max_tdocs):
                return True

        return False


__all__ = [
    "TDocCrawlResult",
    "TDocCrawler",
]
