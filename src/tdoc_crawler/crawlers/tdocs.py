"""TDoc crawler for retrieving metadata from 3GPP HTTP server."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import CrawlLimits, TDocCrawlConfig, TDocMetadata, WorkingGroup

logger = logging.getLogger(__name__)

# TDoc filename pattern: Matches various TDoc formats
# Format: [RSC][1-6P] followed by 4-10 characters, then extension
# Examples: R1-2301234.zip, S4-251209.txt, C1-2312345.pdf, SP-240001.zip, RP-230045.txt
#           S4aA220001.zip (ad-hoc), R1eE230045.txt (ad-hoc), CP-123456.zip (CT plenary)
TDOC_PATTERN = re.compile(r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)", re.IGNORECASE)

# Directories to exclude from crawling
EXCLUDED_DIRS = {"Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report"}
EXCLUDED_DIRS_NORMALIZED = {entry.upper() for entry in EXCLUDED_DIRS}

# Subdirectories that may contain TDocs (case-insensitive matching)
TDOC_SUBDIRS = {"Docs", "Documents", "Tdocs", "TDocs", "DOCS"}
TDOC_SUBDIRS_NORMALIZED = {entry.upper() for entry in TDOC_SUBDIRS}


@dataclass(slots=True, frozen=True)
class TDocCrawlResult:
    """Summary of a TDoc crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


class TDocCrawler:
    """Configuration-driven HTTP crawler for gathering TDoc metadata."""

    def __init__(self, database: TDocDatabase) -> None:
        self.database = database

    def crawl(self, config: TDocCrawlConfig) -> TDocCrawlResult:
        """Execute a crawl using the provided configuration.

        Queries meetings from the database and crawls their HTTP directories for TDocs.
        """
        errors: list[str] = []
        collected: list[TDocMetadata] = []
        seen_ids: set[str] = set()

        # Query meetings from database based on config filters
        meetings = self._get_meetings_to_crawl(config)
        if not meetings:
            logger.warning("No meetings found matching criteria")
            return TDocCrawlResult(processed=0, inserted=0, updated=0, errors=["No meetings found"])

        existing_ids: set[str] = set()
        if config.incremental:
            existing_ids = self.database.get_existing_tdoc_ids(config.working_groups)
        targets: set[str] | None = set(config.target_ids) if config.target_ids else None

        # Create HTTP session with retry logic
        session = self._create_session(config)

        try:
            for meeting in meetings:
                if not meeting.files_url:
                    continue
                try:
                    self._crawl_meeting(
                        session,
                        meeting,
                        config,
                        collected,
                        seen_ids,
                        existing_ids,
                        targets,
                    )
                    if targets is not None and not targets:
                        break
                except Exception as exc:
                    message = f"Error crawling meeting {meeting.short_name}: {exc}"
                    logger.warning(message)
                    errors.append(message)
        except Exception as exc:
            logger.exception("Unexpected TDoc crawl failure")
            errors.append(str(exc))
        finally:
            session.close()

        inserted = 0
        updated = 0
        if collected:
            inserted, updated = self.database.bulk_upsert_tdocs(collected)

        return TDocCrawlResult(
            processed=len(collected),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _limit_working_groups(self, working_groups: list[WorkingGroup], limits: CrawlLimits) -> list[WorkingGroup]:
        if limits.limit_wgs is None or limits.limit_wgs == 0:
            return working_groups
        limit = limits.limit_wgs
        return working_groups[:limit] if limit > 0 else working_groups[limit:]

    def _create_session(self, config: TDocCrawlConfig) -> requests.Session:
        """Create HTTP session with retry logic and timeout configuration."""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set timeout
        session.timeout = config.timeout

        return session

    def _get_meetings_to_crawl(self, config: TDocCrawlConfig) -> list:
        """Query meetings from database based on config filters."""
        from tdoc_crawler.models import MeetingQueryConfig, SortOrder

        # Build meeting query config from TDoc crawl config
        meeting_config = MeetingQueryConfig(
            cache_dir=config.cache_dir,
            working_groups=config.working_groups,
            subgroups=config.subgroups,
            limit=config.limits.limit_meetings,
            order=SortOrder.DESC,
            include_without_files=False,  # Only get meetings with HTTP links
        )

        meetings = self.database.query_meetings(meeting_config)

        # Apply meeting_ids filter if specified
        if config.meeting_ids:
            meeting_id_set = set(config.meeting_ids)
            meetings = [m for m in meetings if m.meeting_id in meeting_id_set]

        # Apply date range filters
        if config.start_date:
            meetings = [m for m in meetings if m.start_date and m.start_date >= config.start_date]
        if config.end_date:
            meetings = [m for m in meetings if m.start_date and m.start_date <= config.end_date]

        return meetings

    def _crawl_meeting(
        self,
        session: requests.Session,
        meeting,  # MeetingMetadata
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> None:
        """Crawl a specific meeting's HTTP directory for TDocs.

        This method first scans the base meeting directory for TDoc subdirectories
        (like "Docs/") and crawls those. If no subdirectories are found, it scans
        the base directory directly.
        """
        base_url = meeting.files_url
        if not base_url.endswith("/"):
            base_url += "/"

        logger.debug("Crawling meeting %s at %s", meeting.short_name, base_url)

        try:
            response = session.get(base_url, timeout=config.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch directory %s: %s", base_url, exc)
            return

        # Parse HTML directory listing
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for TDoc subdirectories (e.g., "Docs/")
        subdirs_found = []
        for link in soup.find_all("a"):
            href = link.get("href")
            if not href or not isinstance(href, str):
                continue

            # Skip query strings and parent directory links
            if href.startswith(("?", "..")):
                continue

            # Extract directory name from href (handles both full URLs and relative paths)
            dir_name = href.rstrip("/").split("/")[-1]

            # Check if this is a TDoc subdirectory
            if dir_name.upper() in TDOC_SUBDIRS_NORMALIZED:
                # Build full URL, ensuring it ends with /
                if href.startswith("http"):
                    subdir_url = href if href.endswith("/") else href + "/"
                else:
                    subdir_url = base_url + href.lstrip("/")
                    if not subdir_url.endswith("/"):
                        subdir_url += "/"
                subdirs_found.append(subdir_url)

        # Crawl subdirectories if found, otherwise crawl base directory
        if subdirs_found:
            for subdir_url in subdirs_found:
                self._scan_directory_for_tdocs(session, subdir_url, meeting, config, collected, seen_ids, existing_ids, targets)
        else:
            # No subdirectories found, scan base directory directly
            self._scan_directory_for_tdocs(session, base_url, meeting, config, collected, seen_ids, existing_ids, targets)

    def _scan_directory_for_tdocs(
        self,
        session: requests.Session,
        directory_url: str,
        meeting,  # MeetingMetadata
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> None:
        """Scan a specific directory URL for TDoc files."""
        if not directory_url.endswith("/"):
            directory_url += "/"

        logger.debug("Scanning directory %s", directory_url)

        try:
            response = session.get(directory_url, timeout=config.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch directory %s: %s", directory_url, exc)
            return

        # Parse HTML directory listing
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract file links from HTML
        for link in soup.find_all("a"):
            if targets is not None and not targets:
                return

            href_value = link.get("href")
            if not href_value or not isinstance(href_value, str):
                continue

            href = str(href_value)

            # Skip parent directory links
            if href in ("../", "/", ".", ".."):
                continue

            # Check if it's a TDoc file
            match = TDOC_PATTERN.search(href)
            if not match:
                continue

            tdoc_id = match.group(1).upper()
            if targets is not None and tdoc_id not in targets:
                continue
            if not self._should_store_tdoc(tdoc_id, seen_ids, existing_ids, config.incremental):
                continue

            # Build absolute URL
            file_url = href if href.startswith(("http://", "https://")) else directory_url + href

            # Try to get file size from HTML content
            file_size = None
            parent = link.parent
            if parent:
                # Look for size information in the same row
                text_content = parent.get_text()
                size_match = re.search(r"(\d+)\s*[KMG]?B", text_content, re.IGNORECASE)
                if size_match:
                    size_str = size_match.group(1)
                    try:
                        file_size = int(size_str)
                        # Check for KB, MB, GB suffixes
                        if "K" in text_content.upper():
                            file_size *= 1024
                        elif "M" in text_content.upper():
                            file_size *= 1024 * 1024
                        elif "G" in text_content.upper():
                            file_size *= 1024 * 1024 * 1024
                    except ValueError:
                        pass

            # Create TDoc metadata with meeting information
            metadata = TDocMetadata(
                tdoc_id=tdoc_id,
                url=file_url,
                working_group=meeting.working_group,
                subgroup=meeting.subgroup,
                meeting=meeting.short_name,
                meeting_id=meeting.meeting_id,
                file_size=file_size,
                title=None,
                contact=None,
                tdoc_type=None,
                for_purpose=None,
                agenda_item=None,
                status=None,
                is_revision_of=None,
                document_type=None,
                checksum=None,
                source_path=directory_url + href,
                date_created=None,
                date_retrieved=datetime.now(UTC),
                validated=False,
                validation_failed=False,
            )
            collected.append(metadata)
            seen_ids.add(tdoc_id)
            if targets is not None:
                targets.discard(tdoc_id)
            if config.verbose:
                logger.debug("Collected TDoc %s from meeting %s", tdoc_id, meeting.short_name)

    def _should_store_tdoc(
        self,
        tdoc_id: str,
        seen_ids: set[str],
        existing_ids: set[str],
        incremental: bool,
    ) -> bool:
        return tdoc_id not in seen_ids and (not incremental or tdoc_id not in existing_ids)


__all__ = ["TDocCrawlResult", "TDocCrawler"]
