"""Crawlers for retrieving TDoc and meeting metadata from 3GPP resources."""

from __future__ import annotations

import contextlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from ftplib import FTP, error_perm, error_temp
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import (
    CrawlLimits,
    MeetingCrawlConfig,
    MeetingMetadata,
    TDocCrawlConfig,
    TDocMetadata,
    WorkingGroup,
)

logger = logging.getLogger(__name__)

TDOC_PATTERN = re.compile(r"([RST]\d+-\d{7})\.(zip|txt)", re.IGNORECASE)
EXCLUDED_DIRS = {"Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report"}
EXCLUDED_DIRS_NORMALIZED = {entry.upper() for entry in EXCLUDED_DIRS}
FTP_HOST = "ftp.3gpp.org"
MEETINGS_BASE_URL = "https://www.3gpp.org/dynareport?code=Meetings-{code}.htm"
PORTAL_BASE_URL = "https://portal.3gpp.org"
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

MEETING_CODE_REGISTRY: dict[WorkingGroup, list[tuple[str, str | None]]] = {
    WorkingGroup.RAN: [
        ("RP", "RAN Plenary"),
        ("R1", "RAN1"),
        ("R2", "RAN2"),
        ("R3", "RAN3"),
        ("R4", "RAN4"),
        ("R5", "RAN5"),
        ("R6", "RAN6"),
    ],
    WorkingGroup.SA: [
        ("SP", "SA Plenary"),
        ("S1", "SA1"),
        ("S2", "SA2"),
        ("S3", "SA3"),
        ("S4", "SA4"),
        ("S5", "SA5"),
        ("S6", "SA6"),
    ],
    WorkingGroup.CT: [
        ("CP", "CT Plenary"),
        ("C1", "CT1"),
        ("C2", "CT2"),
        ("C3", "CT3"),
        ("C4", "CT4"),
        ("C5", "CT5"),
        ("C6", "CT6"),
    ],
}


@dataclass(slots=True, frozen=True)
class TDocCrawlResult:
    """Summary of a TDoc crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


@dataclass(slots=True, frozen=True)
class MeetingCrawlResult:
    """Summary of a meeting crawl run."""

    processed: int
    inserted: int
    updated: int
    errors: list[str]


class TDocCrawler:
    """Configuration-driven FTP crawler for gathering TDoc metadata."""

    def __init__(self, database: TDocDatabase) -> None:
        self.database = database

    def crawl(self, config: TDocCrawlConfig) -> TDocCrawlResult:
        """Execute a crawl using the provided configuration."""

        errors: list[str] = []
        collected: list[TDocMetadata] = []
        seen_ids: set[str] = set()

        working_groups = self._limit_working_groups(config.working_groups, config.limits)
        existing_ids: set[str] = set()
        if config.incremental:
            existing_ids = self.database.get_existing_tdoc_ids(working_groups)
        targets: set[str] | None = set(config.target_ids) if config.target_ids else None

        ftp: FTP | None = None
        try:
            ftp = self._connect(config)
            for working_group in working_groups:
                try:
                    self._crawl_working_group(
                        ftp,
                        working_group,
                        config,
                        collected,
                        seen_ids,
                        existing_ids,
                        targets,
                    )
                    if targets is not None and not targets:
                        break
                except Exception as exc:
                    message = f"Error crawling {working_group.value}: {exc}"
                    logger.warning(message)
                    errors.append(message)
        except Exception as exc:
            logger.exception("Unexpected TDoc crawl failure")
            errors.append(str(exc))
        finally:
            if ftp is not None:
                with contextlib.suppress(Exception):
                    ftp.quit()

        filtered = collected if targets is not None else self._apply_limits(collected, config.limits)
        inserted = 0
        updated = 0
        if filtered:
            inserted, updated = self.database.bulk_upsert_tdocs(filtered)

        return TDocCrawlResult(
            processed=len(filtered),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _limit_working_groups(self, working_groups: list[WorkingGroup], limits: CrawlLimits) -> list[WorkingGroup]:
        if limits.limit_wgs is None or limits.limit_wgs == 0:
            return working_groups
        limit = limits.limit_wgs
        return working_groups[:limit] if limit > 0 else working_groups[limit:]

    def _connect(self, config: TDocCrawlConfig, attempt: int = 0) -> FTP:
        try:
            ftp = FTP(FTP_HOST, timeout=config.timeout)  # noqa: S321
            ftp.login()
            ftp.encoding = "utf-8"
        except (error_temp, error_perm, OSError):
            if attempt < config.max_retries:
                logger.warning("FTP connection failed (attempt %s), retrying", attempt + 1)
                return self._connect(config, attempt + 1)
            raise
        return ftp

    def _crawl_working_group(
        self,
        ftp: FTP,
        working_group: WorkingGroup,
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> None:
        ftp.cwd("/")
        path = working_group.ftp_root
        ftp.cwd(path)
        self._crawl_directory(
            ftp,
            working_group,
            path,
            [],
            config,
            collected,
            seen_ids,
            existing_ids,
            targets,
        )

    def _crawl_directory(
        self,
        ftp: FTP,
        working_group: WorkingGroup,
        full_path: str,
        path_parts: list[str],
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> None:
        entries: list[str] = []
        ftp.retrlines("LIST", entries.append)
        for entry in entries:
            if targets is not None and not targets:
                return
            tokens = entry.split()
            if len(tokens) < 9:
                continue
            is_dir = entry.startswith("d")
            name = " ".join(tokens[8:])

            if is_dir:
                if self._should_skip_directory(name):
                    continue
                try:
                    ftp.cwd(name)
                    self._crawl_directory(
                        ftp,
                        working_group,
                        f"{full_path}/{name}",
                        [*path_parts, name],
                        config,
                        collected,
                        seen_ids,
                        existing_ids,
                        targets,
                    )
                except error_perm:
                    logger.debug("Permission denied for directory %s", name)
                finally:
                    with contextlib.suppress(Exception):
                        ftp.cwd("..")
                continue

            self._process_file(
                tokens,
                name,
                working_group,
                full_path,
                path_parts,
                config,
                collected,
                seen_ids,
                existing_ids,
                targets,
            )

    def _should_skip_directory(self, name: str) -> bool:
        return name.startswith(".") or name.upper() in EXCLUDED_DIRS_NORMALIZED

    def _process_file(
        self,
        entry_tokens: list[str],
        name: str,
        working_group: WorkingGroup,
        full_path: str,
        path_parts: list[str],
        config: TDocCrawlConfig,
        collected: list[TDocMetadata],
        seen_ids: set[str],
        existing_ids: set[str],
        targets: set[str] | None,
    ) -> None:
        match = TDOC_PATTERN.search(name)
        if not match:
            return
        tdoc_id = match.group(1).upper()
        if targets is not None and tdoc_id not in targets:
            return
        if not self._should_store_tdoc(tdoc_id, seen_ids, existing_ids, config.incremental):
            return

        file_size = int(entry_tokens[4]) if len(entry_tokens) > 4 else None
        meeting = path_parts[-1] if path_parts else None
        subgroup = self._extract_subgroup(path_parts, working_group)
        metadata = TDocMetadata(
            tdoc_id=tdoc_id,
            url=f"ftp://{FTP_HOST}{full_path}/{name}",
            working_group=working_group,
            subgroup=subgroup,
            meeting=meeting,
            meeting_id=None,
            file_size=file_size,
            document_type=None,
            checksum=None,
            source_path=f"{full_path}/{name}",
            date_created=None,
            date_retrieved=datetime.now(UTC),
        )
        collected.append(metadata)
        seen_ids.add(tdoc_id)
        if targets is not None:
            targets.discard(tdoc_id)
        if config.verbose:
            logger.debug("Collected TDoc %s", tdoc_id)

    def _should_store_tdoc(
        self,
        tdoc_id: str,
        seen_ids: set[str],
        existing_ids: set[str],
        incremental: bool,
    ) -> bool:
        return tdoc_id not in seen_ids and (not incremental or tdoc_id not in existing_ids)

    def _extract_subgroup(self, path_parts: list[str], working_group: WorkingGroup) -> str | None:
        if not path_parts:
            return None
        parent = path_parts[0].upper()
        if parent.startswith(f"TSG_{working_group.value}"):
            return f"{working_group.value} Plenary"
        if parent.startswith(working_group.value):
            return parent
        return None

    def _apply_limits(self, records: list[TDocMetadata], limits: CrawlLimits) -> list[TDocMetadata]:
        if not records:
            return []
        filtered = list(records)
        filtered = self._limit_meetings_per_wg(filtered, limits.limit_meetings_per_wg)
        filtered = self._limit_meetings(filtered, limits.limit_meetings)
        filtered = self._limit_tdocs(filtered, limits.limit_tdocs)
        return filtered

    def _limit_meetings_per_wg(
        self,
        records: list[TDocMetadata],
        limit: int | None,
    ) -> list[TDocMetadata]:
        if limit is None or limit == 0:
            return records
        meeting_sequence: dict[WorkingGroup, list[str | None]] = defaultdict(list)
        for record in records:
            sequence = meeting_sequence[record.working_group]
            if record.meeting not in sequence:
                sequence.append(record.meeting)
        allowed_meetings: dict[WorkingGroup, set[str | None]] = {}
        for working_group, sequence in meeting_sequence.items():
            selected = sequence[:limit] if limit > 0 else sequence[limit:]
            allowed_meetings[working_group] = set(selected)
        return [record for record in records if record.meeting in allowed_meetings.get(record.working_group, {record.meeting})]

    def _limit_meetings(self, records: list[TDocMetadata], limit: int | None) -> list[TDocMetadata]:
        if limit is None or limit == 0:
            return records
        sequence: list[str | None] = []
        for record in records:
            if record.meeting not in sequence:
                sequence.append(record.meeting)
        allowed = set(sequence[:limit]) if limit > 0 else set(sequence[limit:])
        return [record for record in records if record.meeting in allowed]

    def _limit_tdocs(self, records: list[TDocMetadata], limit: int | None) -> list[TDocMetadata]:
        if limit is None or limit == 0:
            return records
        return records[:limit] if limit > 0 else records[limit:]


class MeetingCrawler:
    """Crawler fetching meeting metadata from the 3GPP portal."""

    def __init__(self, database: TDocDatabase) -> None:
        self.database = database

    def crawl(self, config: MeetingCrawlConfig) -> MeetingCrawlResult:
        errors: list[str] = []
        meetings: list[MeetingMetadata] = []

        working_groups = self._limit_working_groups(config.working_groups, config.limits)
        existing_ids: set[int] = set()
        if config.incremental:
            existing_ids = self.database.get_existing_meeting_ids(working_groups)
        session = requests.Session()
        session.headers["User-Agent"] = "tdoc-crawler/0.0.1"
        if config.credentials is not None:
            session.auth = (config.credentials.username, config.credentials.password)

        try:
            for working_group in working_groups:
                for code, subgroup in MEETING_CODE_REGISTRY.get(working_group, []):
                    url = MEETINGS_BASE_URL.format(code=code)
                    try:
                        response = session.get(url, timeout=config.timeout)
                        response.raise_for_status()
                    except requests.RequestException as exc:
                        message = f"Meeting crawl failed for {code}: {exc}"
                        logger.warning(message)
                        errors.append(message)
                        continue
                    parsed_meetings = self._parse_meeting_page(response.text, working_group, subgroup)
                    for meeting in parsed_meetings:
                        if config.incremental and meeting.meeting_id in existing_ids:
                            continue
                        meetings.append(meeting)
        finally:
            session.close()

        filtered = self._apply_limits(meetings, config.limits)
        inserted = 0
        updated = 0
        if filtered:
            inserted, updated = self.database.bulk_upsert_meetings(filtered)

        return MeetingCrawlResult(
            processed=len(filtered),
            inserted=inserted,
            updated=updated,
            errors=errors,
        )

    def _limit_working_groups(self, working_groups: list[WorkingGroup], limits: CrawlLimits) -> list[WorkingGroup]:
        if limits.limit_wgs is None or limits.limit_wgs == 0:
            return working_groups
        limit = limits.limit_wgs
        return working_groups[:limit] if limit > 0 else working_groups[limit:]

    def _parse_meeting_page(
        self,
        html: str,
        working_group: WorkingGroup,
        subgroup: str | None,
    ) -> list[MeetingMetadata]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if table is None:
            return []
        meetings: list[MeetingMetadata] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            try:
                meetings.append(self._parse_meeting_row(cells, working_group, subgroup))
            except ValueError as exc:
                logger.debug("Skipping meeting row: %s", exc)
        return meetings

    def _parse_meeting_row(
        self,
        cells: list[Tag],
        working_group: WorkingGroup,
        subgroup: str | None,
    ) -> MeetingMetadata:
        short_name, portal_url, meeting_id = self._extract_meeting_reference(cells[0])
        title = cells[1].get_text(strip=True) if len(cells) > 1 else None
        date_text = cells[2].get_text(" ", strip=True) if len(cells) > 2 else ""
        start_date, end_date = self._parse_dates(date_text)
        location = cells[3].get_text(" ", strip=True) if len(cells) > 3 else None
        files_url = self._extract_first_link(cells[-1])
        return MeetingMetadata(
            meeting_id=meeting_id,
            working_group=working_group,
            subgroup=subgroup,
            short_name=short_name,
            title=title or None,
            start_date=start_date,
            end_date=end_date,
            location=location or None,
            files_url=files_url,
            portal_url=portal_url,
        )

    def _extract_meeting_reference(self, cell: Tag) -> tuple[str, str | None, int]:
        short_name = cell.get_text(strip=True)
        link = cell.find("a")
        if link is None:
            raise ValueError("missing-meeting-link")
        raw_href = link.get("href")
        if raw_href is None:
            raise ValueError("missing-meeting-link")
        href = str(raw_href)
        portal_url = href if href.startswith("http") else urljoin(PORTAL_BASE_URL, href)
        match = re.search(r"MtgId=(\d+)", href)
        if match is None:
            raise ValueError("missing-meeting-id")
        meeting_id = int(match.group(1))
        return short_name, portal_url, meeting_id

    def _extract_first_link(self, cell: Tag) -> str | None:
        link = cell.find("a")
        if link is None:
            return None
        raw_href = link.get("href")
        if raw_href is None:
            return None
        href = str(raw_href)
        return href if href.startswith("http") else urljoin("https://www.3gpp.org", href)

    def _parse_dates(self, text: str) -> tuple[date | None, date | None]:
        matches = DATE_PATTERN.findall(text)
        if not matches:
            return None, None
        start = date.fromisoformat(matches[0])
        end = date.fromisoformat(matches[-1]) if len(matches) > 1 else start
        return start, end

    def _apply_limits(self, meetings: list[MeetingMetadata], limits: CrawlLimits) -> list[MeetingMetadata]:
        if not meetings:
            return []
        filtered = list(meetings)
        filtered = self._limit_meetings_per_wg(filtered, limits.limit_meetings_per_wg)
        filtered = self._limit_meetings(filtered, limits.limit_meetings)
        return filtered

    def _limit_meetings_per_wg(
        self,
        meetings: list[MeetingMetadata],
        limit: int | None,
    ) -> list[MeetingMetadata]:
        if limit is None or limit == 0:
            return meetings
        order: dict[WorkingGroup, list[int]] = defaultdict(list)
        for meeting in meetings:
            sequence = order[meeting.working_group]
            if meeting.meeting_id not in sequence:
                sequence.append(meeting.meeting_id)
        allowed_ids: dict[WorkingGroup, set[int]] = {}
        for working_group, sequence in order.items():
            selected = sequence[:limit] if limit > 0 else sequence[limit:]
            allowed_ids[working_group] = set(selected)
        return [meeting for meeting in meetings if meeting.meeting_id in allowed_ids.get(meeting.working_group, {meeting.meeting_id})]

    def _limit_meetings(self, meetings: list[MeetingMetadata], limit: int | None) -> list[MeetingMetadata]:
        if limit is None or limit == 0:
            return meetings
        sequence: list[int] = []
        for meeting in meetings:
            if meeting.meeting_id not in sequence:
                sequence.append(meeting.meeting_id)
        allowed = set(sequence[:limit]) if limit > 0 else set(sequence[limit:])
        return [meeting for meeting in meetings if meeting.meeting_id in allowed]


if __name__ == "__main__":
    pass
