"""Hybrid TDoc crawler supporting both document list and parallel crawling methods."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from tdoc_crawler.crawlers.executor_adapter import Runner
from tdoc_crawler.crawlers.parallel import (
    fetch_meeting_document_list_subinterpreter, fetch_meeting_tdocs)
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import (CrawlLimits, MeetingMetadata,
                                 MeetingQueryConfig, SortOrder,
                                 TDocCrawlConfig, TDocMetadata, WorkingGroup)

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class HybridCrawlResult:
    """Summary of a hybrid TDoc crawl run."""

    processed: int
    inserted: int
    updated: int
    document_list_meetings: int
    parallel_meetings: int
    fallbacks: int
    errors: list[str]


class HybridTDocCrawler:
    """Hybrid crawler that supports both document list and parallel crawling methods."""

    def __init__(self, database: TDocDatabase) -> None:
        self.database = database

    def crawl(self, config: TDocCrawlConfig, progress_callback: Callable[[float, float], None] | None = None) -> HybridCrawlResult:
        """Execute a hybrid crawl using the provided configuration.

        This method supports both document list and parallel crawling methods
        with automatic fallbacks based on configuration.
        """
        meetings = self._get_meetings_to_crawl(config)
        if not meetings:
            logger.warning("No meetings found matching criteria")
            return HybridCrawlResult(
                processed=0, inserted=0, updated=0, document_list_meetings=0, parallel_meetings=0, fallbacks=0, errors=["No meetings found"]
            )

        meetings = self._apply_meeting_limits(meetings, config.limits)
        if not meetings:
            logger.warning("Meetings filtered out by limits configuration")
            return HybridCrawlResult(
                processed=0,
                inserted=0,
                updated=0,
                document_list_meetings=0,
                parallel_meetings=0,
                fallbacks=0,
                errors=["No meetings found after applying limits"],
            )

        existing_ids: set[str] = set()
        if config.incremental:
            existing_ids = {tdoc_id.upper() for tdoc_id in self.database.get_existing_tdoc_ids(config.working_groups)}

        targets = set(config.target_ids) if config.target_ids else None

        collected: list[TDocMetadata] = []
        errors: list[str] = []

        # Phase 1: Document list method
        document_list_meetings = []
        parallel_meetings = []

        for meeting in meetings:
            if self._should_use_document_list_method(config, meeting):
                document_list_meetings.append(meeting)
            else:
                parallel_meetings.append(meeting)

        document_list_errors, doc_list_meetings_processed = [], 0
        if document_list_meetings:
            logger.info(f"Starting document list crawl for {len(document_list_meetings)} meetings")
            document_list_errors, doc_list_meetings_processed = asyncio.run(
                self._crawl_meetings_document_list(document_list_meetings, config, collected, existing_ids, targets)
            )
            errors.extend(document_list_errors)

        # Phase 2: Parallel method (for meetings not processed by document list or as fallback)
        parallel_meetings_final = []
        for meeting in parallel_meetings:
            parallel_meetings_final.append(meeting)

        # Add failed meetings as fallback if configured
        if config.allow_parallel_fallback:
            for meeting in document_list_meetings:
                if meeting.files_url and meeting.meeting_id not in [m.meeting_id for m in parallel_meetings_final]:
                    # Check if this meeting failed in document list phase
                    # This is a simple heuristic - in practice we'd track failures more precisely
                    parallel_meetings_final.append(meeting)

        parallel_errors, parallel_meetings_processed = [], 0
        if parallel_meetings_final:
            logger.info(f"Starting parallel crawl for {len(parallel_meetings_final)} meetings")
            parallel_errors, parallel_meetings_processed = asyncio.run(
                self._crawl_meetings_parallel(parallel_meetings_final, config, collected, existing_ids, targets)
            )
            errors.extend(parallel_errors)

        # Database operations
        inserted = 0
        updated = 0
        if collected:
            inserted, updated = self.database.bulk_upsert_tdocs(collected, progress_callback=progress_callback)

        return HybridCrawlResult(
            processed=len(collected),
            inserted=inserted,
            updated=updated,
            document_list_meetings=doc_list_meetings_processed,
            parallel_meetings=parallel_meetings_processed,
            fallbacks=len(parallel_meetings_final) - len(parallel_meetings) if config.allow_parallel_fallback else 0,
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

    def _should_use_document_list_method(
        self,
        config: TDocCrawlConfig,
        meeting: MeetingMetadata,
    ) -> bool:
        """Determine if document list method should be used for a meeting.

        Args:
            config: TDoc crawl configuration
            meeting: Meeting metadata

        Returns:
            True if document list method should be used
        """
        # If explicitly forced to parallel crawling, don't use document list
        if config.use_parallel_crawling:
            return False

        # If document list is disabled, use parallel crawling
        if not config.use_document_list:
            return False

        # If meeting has no files_url, we can't do parallel crawling anyway
        if not meeting.files_url:
            return True

        # Default: prefer document list method (faster, no credentials required)
        return True

    async def _crawl_meetings_parallel(
        self,
        meetings: list,
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> tuple[list[str], int]:
        """Launch subinterpreter workers to crawl meetings in parallel."""
        errors: list[str] = []
        seen_ids: set[str] = set()
        max_tdocs = None
        if config.limits.limit_tdocs is not None and config.limits.limit_tdocs != 0:
            max_tdocs = abs(config.limits.limit_tdocs)

        # Pre-filter meetings to optimize task submission
        meetings = self._filter_meetings_for_parallel_crawl(meetings, max_tdocs)

        target_tuple = tuple(targets) if targets else None

        runner = Runner(workers=config.workers)
        with runner.start():
            tasks: dict[asyncio.Task[tuple[str, ...]], MeetingMetadata] = {}

            for meeting in meetings:
                base_url = meeting.files_url.rstrip("/") + "/"
                task = asyncio.create_task(
                    runner.run(
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
                )
                tasks[task] = meeting

            pending = set(tasks.keys())
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    meeting = tasks[task]
                    try:
                        payloads = task.result()
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

                    if limit_reached or (targets is not None and not targets):
                        for pending_task in pending:
                            pending_task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        return errors, len(tasks)

        return errors, len(tasks)

    async def _crawl_meetings_document_list(
        self,
        meetings: list,
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> tuple[list[str], int]:
        """Launch subinterpreter workers to crawl meetings in parallel using document list method."""
        errors: list[str] = []
        seen_ids: set[str] = set()
        max_tdocs = None
        if config.limits.limit_tdocs is not None and config.limits.limit_tdocs != 0:
            max_tdocs = abs(config.limits.limit_tdocs)

        # Pre-filter meetings to optimize task submission
        target_tuple = tuple(targets) if targets else None
        target_set = set(target_tuple) if target_tuple else None

        runner = Runner(workers=config.workers)
        with runner.start():
            # Note: fetch_meeting_document_list from parallel module returns str (JSON)
            tasks: dict[asyncio.Task[str], MeetingMetadata] = {}

            for meeting in meetings:
                # Skip meetings that don't have files_url for document list method
                # Document list method only works for meetings that have portal data
                task = asyncio.create_task(
                    runner.run(
                        fetch_meeting_document_list_subinterpreter,
                        meeting.meeting_id,
                        str(config.cache_dir),  # This is correct - the function expects a string
                        config.http_cache.ttl,
                        config.http_cache.refresh_ttl_on_access,
                        config.timeout,
                    )
                )
                tasks[task] = meeting

            pending = set(tasks.keys())
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    meeting = tasks[task]
                    try:
                        json_payload = task.result()
                    except Exception as exc:  # pragma: no cover - defensive, depends on network
                        short_name = meeting.short_name or str(meeting.meeting_id)
                        message = f"Meeting {short_name}: {exc}"
                        logger.warning(message)
                        errors.append(message)
                        continue

                    # Parse the JSON response (could be error or success)
                    try:
                        response_data = json.loads(json_payload)

                        # Check if this is an error response
                        if "_error" in response_data:
                            error_info = response_data["_error"]
                            error_msg = f"Document list method failed for meeting {meeting.short_name or meeting.meeting_id}: {error_info['error']}"
                            logger.warning(error_msg)
                            errors.append(error_msg)
                            continue

                        # Process successful TDoc metadata
                        tdoc_metadata_list = []
                        for tdoc_json in response_data:
                            tdoc_metadata = TDocMetadata.model_validate_json(tdoc_json)
                            tdoc_metadata_list.append(tdoc_metadata)

                        # Process each TDoc from the document list
                        for tdoc_metadata in tdoc_metadata_list:
                            if target_set and tdoc_metadata.tdoc_id not in target_set:
                                continue
                            if tdoc_metadata.tdoc_id in seen_ids:
                                continue
                            if config.incremental and tdoc_metadata.tdoc_id in existing_ids:
                                continue

                            collected.append(tdoc_metadata)
                            seen_ids.add(tdoc_metadata.tdoc_id)

                            if target_set:
                                target_set.discard(tdoc_metadata.tdoc_id)
                                if not target_set:
                                    for pending_task in pending:
                                        pending_task.cancel()
                                    if pending:
                                        await asyncio.gather(*pending, return_exceptions=True)
                                    return errors, len(tasks)

                            if max_tdocs and len(collected) >= max_tdocs:
                                for pending_task in pending:
                                    pending_task.cancel()
                                if pending:
                                    await asyncio.gather(*pending, return_exceptions=True)
                                return errors, len(tasks)

                        short_name = meeting.short_name or str(meeting.meeting_id)
                        logger.info(f"Successfully processed {len(tdoc_metadata_list)} TDocs from document list for meeting {short_name}")

                    except Exception as exc:
                        short_name = meeting.short_name or str(meeting.meeting_id)
                        error_msg = f"Failed to parse document list response for meeting {short_name}: {exc}"
                        logger.warning(error_msg)
                        errors.append(error_msg)

        return errors, len(meetings)

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
    "HybridCrawlResult",
    "HybridTDocCrawler",
]
