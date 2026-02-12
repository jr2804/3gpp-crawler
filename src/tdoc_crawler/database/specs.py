"""Spec database and crawling operations."""

from __future__ import annotations

import contextlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.logging import get_logger
from tdoc_crawler.specs.models import (
    Specification,
    SpecificationDownload,
    SpecificationSourceRecord,
    SpecificationVersion,
    SpecQueryFilters,
    SpecQueryResult,
)
from tdoc_crawler.specs.sources.base import SpecSource
from tdoc_crawler.utils.normalization import normalize_spec_number

_logger = get_logger(__name__)


@dataclass(frozen=True)
class SpecCrawlSourceOutcome:
    """Outcome for a single spec source crawl."""

    source_name: str
    status: str
    versions: list[str]
    message: str | None = None


@dataclass(frozen=True)
class SpecCrawlResult:
    """Aggregated crawl result for a spec number."""

    spec_number: str
    release: str
    status: str
    latest_version: str | None
    sources: list[SpecCrawlSourceOutcome]
    message: str | None = None


class SpecDatabase(DocDatabase):
    """Database and crawler for specification metadata."""

    # ------------------------------------------------------------------
    # Spec operations
    # ------------------------------------------------------------------
    def upsert_specification(self, specification: Specification) -> tuple[bool, bool]:
        """Upsert a specification record."""
        existing = self._get_specification(specification.spec_number)
        if existing is None:
            self.connection.add("specs", specification, pk="spec_number")
            return True, False

        changed = self._spec_changed(existing, specification)
        self.connection.add("specs", specification, pk="spec_number")
        return False, changed

    def upsert_spec_source_record(self, record: SpecificationSourceRecord) -> tuple[bool, bool]:
        """Upsert a spec source record."""
        record_id = record.record_id or f"{record.spec_number}:{record.source_name}"
        updated_record = record.model_copy(update={"record_id": record_id})
        existing = self._get_spec_source_record(record_id)
        if existing is None:
            self.connection.add("spec_source_records", updated_record, pk="record_id")
            return True, False

        changed = self._spec_source_changed(existing, updated_record)
        self.connection.add("spec_source_records", updated_record, pk="record_id")
        return False, changed

    def upsert_spec_version(self, version: SpecificationVersion) -> tuple[bool, bool]:
        """Upsert a spec version record."""
        record_id = version.record_id or f"{version.spec_number}:{version.version}:{version.source_name}"
        updated_version = version.model_copy(update={"record_id": record_id})
        existing = self._get_spec_version(record_id)
        if existing is None:
            self.connection.add("spec_versions", updated_version, pk="record_id")
            return True, False

        changed = self._spec_version_changed(existing, updated_version)
        self.connection.add("spec_versions", updated_version, pk="record_id")
        return False, changed

    def get_spec_versions(self, spec_number: str) -> list[SpecificationVersion]:
        """Get all versions for a spec."""
        try:
            cursor = self.connection._db.execute("SELECT * FROM spec_versions WHERE spec_number = ?", (spec_number,))
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            result = []
            for row in rows:
                row_dict = dict(zip(columns, row, strict=False))
                result.append(SpecificationVersion(**row_dict))
            return result
        except Exception:
            return []

    def log_spec_download(self, download: SpecificationDownload) -> None:
        """Persist download/extraction outcomes for a spec version."""
        record_id = download.record_id or f"{download.spec_number}:{download.version}"
        # Convert Path objects to strings for SQLite compatibility
        updated_download = download.model_copy(
            update={
                "record_id": record_id,
                "checkout_path": str(download.checkout_path),
                "document_path": str(download.document_path),
                "attachment_paths": [str(p) for p in download.attachment_paths],
            }
        )
        self.connection.add("spec_downloads", updated_download, pk="record_id")

    def query_specs(self, filters: SpecQueryFilters) -> list[SpecQueryResult]:
        """Query stored spec metadata."""
        specs = self._spec_table_rows()
        source_records = self._table_rows("spec_source_records")
        records_by_spec: dict[str, list[SpecificationSourceRecord]] = defaultdict(list)
        for record in source_records:
            records_by_spec[record.spec_number].append(record)

        if filters.spec_numbers:
            allowed = {normalize_spec_number(value) for value in filters.spec_numbers}
            specs = [spec for spec in specs if spec.spec_number in allowed]

        if filters.title:
            needle = filters.title.strip().lower()
            specs = [spec for spec in specs if needle in (spec.title or "").lower()]

        if filters.working_group:
            needle = filters.working_group.strip().lower()
            specs = [spec for spec in specs if (spec.working_group or "").lower() == needle]

        if filters.status:
            needle = filters.status.strip().lower()
            specs = [spec for spec in specs if (spec.status or "").lower() == needle]

        def build_source_differences(records: list[SpecificationSourceRecord]) -> dict[str, dict[str, str | None]]:
            if len(records) < 2:
                return {}

            fields = ("title", "status", "working_group", "latest_version", "spec_type", "series")
            differences: dict[str, dict[str, str | None]] = {}
            for field in fields:
                values: dict[str, str | None] = {}
                normalized_values: set[str] = set()
                for record in records:
                    payload = record.metadata_payload
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            payload = {}
                    if not isinstance(payload, dict):
                        payload = {}
                    raw_value = payload.get(field)
                    value = str(raw_value) if raw_value is not None else None
                    values[record.source_name] = value
                    normalized_values.add((value or "").strip().lower())

                if len(normalized_values) > 1:
                    differences[field] = values

            return differences

        return [
            SpecQueryResult(
                spec_number=spec.spec_number,
                title=spec.title,
                status=spec.status,
                working_group=spec.working_group,
                source_differences=build_source_differences(records_by_spec.get(spec.spec_number, [])),
            )
            for spec in specs
        ]

    def clear_specs(self) -> dict[str, int]:
        """Clear all spec-related records from database.

        Returns:
            Mapping of table name to deleted row count.
        """
        return self._clear_tables(["spec_downloads", "spec_versions", "spec_source_records", "specs"])

    def crawl_specs(self, spec_numbers: list[str], release: str, sources: list[SpecSource]) -> list[SpecCrawlResult]:
        """Crawl and store spec metadata for the provided spec numbers.

        Args:
            spec_numbers: Spec numbers to crawl.
            release: Release selector; use "latest" for newest version.
            sources: Spec metadata sources.

        Returns:
            List of crawl outcomes for each requested spec.
        """
        results: list[SpecCrawlResult] = []
        for raw_spec in spec_numbers:
            normalized = normalize_spec_number(raw_spec)
            compact = normalized.replace(".", "")
            outcomes: list[SpecCrawlSourceOutcome] = []
            source_records: list[SpecificationSourceRecord] = []
            spec_versions: list[SpecificationVersion] = []
            aggregated: Specification | None = None

            for source in sources:
                try:
                    payload = source.fetch(normalized)
                except Exception as exc:  # noqa: BLE001
                    _logger.warning("Spec crawl failed for %s (%s)", normalized, source.name, exc_info=exc)
                    outcomes.append(
                        SpecCrawlSourceOutcome(
                            source_name=source.name,
                            status="error",
                            versions=[],
                            message=str(exc),
                        )
                    )
                    continue

                source_name = str(payload.get("source_name", source.name))
                source_identifier = payload.get("source_identifier")
                metadata_payload = payload.get("metadata_payload")
                if not isinstance(metadata_payload, dict):
                    metadata_payload = {}

                versions = payload.get("versions")
                if not isinstance(versions, list):
                    versions = []
                normalized_versions = [str(item) for item in versions]

                outcomes.append(
                    SpecCrawlSourceOutcome(
                        source_name=source_name,
                        status="ok",
                        versions=normalized_versions,
                    )
                )

                source_records.append(
                    SpecificationSourceRecord(
                        spec_number=normalized,
                        source_name=source_name,
                        source_identifier=source_identifier if isinstance(source_identifier, str) else None,
                        metadata_payload=metadata_payload,
                        versions=normalized_versions,
                    )
                )

                title = str(metadata_payload.get("title", "Unknown"))
                spec_type = str(metadata_payload.get("spec_type", "TS"))
                status = str(metadata_payload.get("status", "unknown"))
                working_group = str(metadata_payload.get("working_group", "unknown"))
                series = str(metadata_payload.get("series", f"{normalized.split('.')[0]}_series"))
                latest_version = metadata_payload.get("latest_version")
                if latest_version is None and normalized_versions:
                    latest_version = normalized_versions[0]

                candidate = Specification(
                    spec_number=normalized,
                    spec_number_compact=compact,
                    spec_type=spec_type,
                    title=title,
                    status=status,
                    working_group=working_group,
                    series=series,
                    latest_version=str(latest_version) if latest_version is not None else None,
                )
                if aggregated is None:
                    aggregated = candidate
                elif aggregated.latest_version is None and candidate.latest_version is not None:
                    aggregated = aggregated.model_copy(update={"latest_version": candidate.latest_version})

                for i, version in enumerate(normalized_versions):
                    # Try to get specific file name for this version from payload
                    file_name = f"{compact}-unknown.zip"
                    if "specfile" in metadata_payload and isinstance(metadata_payload["specfile"], list):
                        if i < len(metadata_payload["specfile"]):
                            file_name = str(metadata_payload["specfile"][i])
                    elif "file_name" in metadata_payload:
                        file_name = str(metadata_payload["file_name"])

                    spec_versions.append(
                        SpecificationVersion(
                            spec_number=normalized,
                            version=str(version),
                            file_name=file_name,
                            source_name=source_name,
                        )
                    )

            if not outcomes:
                results.append(
                    SpecCrawlResult(
                        spec_number=normalized,
                        release=release,
                        status="error",
                        latest_version=None,
                        sources=[],
                        message="no-sources",
                    )
                )
                continue

            # Check if 3GPP source failed - if so, skip this spec entirely
            threegpp_outcome = next((o for o in outcomes if o.source_name == "3gpp"), None)
            if threegpp_outcome is not None and threegpp_outcome.status == "error":
                _logger.warning("Skipping spec %s due to 3GPP source error", normalized)
                results.append(
                    SpecCrawlResult(
                        spec_number=normalized,
                        release=release,
                        status="skipped",
                        latest_version=None,
                        sources=outcomes,
                        message="3gpp-source-error",
                    )
                )
                continue

            release_matches = release == "latest" or any(release in outcome.versions for outcome in outcomes if outcome.status == "ok")
            if not release_matches:
                results.append(
                    SpecCrawlResult(
                        spec_number=normalized,
                        release=release,
                        status="skipped",
                        latest_version=aggregated.latest_version if aggregated else None,
                        sources=outcomes,
                        message="release-not-found",
                    )
                )
                continue

            if aggregated is None:
                results.append(
                    SpecCrawlResult(
                        spec_number=normalized,
                        release=release,
                        status="error",
                        latest_version=None,
                        sources=outcomes,
                        message="no-metadata",
                    )
                )
                continue

            for record in source_records:
                self.upsert_spec_source_record(record)
            self.upsert_specification(aggregated)
            for version in spec_versions:
                self.upsert_spec_version(version)

            results.append(
                SpecCrawlResult(
                    spec_number=normalized,
                    release=release,
                    status="stored",
                    latest_version=aggregated.latest_version,
                    sources=outcomes,
                )
            )

        return results

    def _spec_table_rows(self) -> list[Specification]:
        return self._table_rows("specs")

    def _get_specification(self, spec_number: str) -> Specification | None:
        try:
            return self.connection.model_from_table("specs", spec_number)  # type: ignore[arg-type]
        except KeyError:
            return None

    def _get_spec_source_record(self, record_id: str) -> SpecificationSourceRecord | None:
        try:
            # Use raw query to handle JSON deserialization manually before model instantiation
            cursor = self.connection._db.execute("SELECT * FROM spec_source_records WHERE record_id = ?", (record_id,))
            row = cursor.fetchone()
            if row is None:
                return None

            columns = [description[0] for description in cursor.description]
            row_dict = dict(zip(columns, row, strict=False))

            # Handle JSON fields
            if "metadata_payload" in row_dict and isinstance(row_dict["metadata_payload"], str):
                try:
                    row_dict["metadata_payload"] = json.loads(row_dict["metadata_payload"])
                except json.JSONDecodeError:
                    row_dict["metadata_payload"] = {}

            if "versions" in row_dict and isinstance(row_dict["versions"], str):
                try:
                    row_dict["versions"] = json.loads(row_dict["versions"])
                except json.JSONDecodeError:
                    row_dict["versions"] = []

            # Handle datetime deserialization
            if "fetched_at" in row_dict and isinstance(row_dict["fetched_at"], str):
                with contextlib.suppress(ValueError, AttributeError):
                    row_dict["fetched_at"] = datetime.fromisoformat(row_dict["fetched_at"])

            return SpecificationSourceRecord(**row_dict)
        except Exception as exc:
            _logger.debug("Error fetching spec source record %s: %s", record_id, exc)
            return None

    def _get_spec_version(self, record_id: str) -> SpecificationVersion | None:
        try:
            return self.connection.model_from_table("spec_versions", record_id)
        except KeyError:
            return None

    @staticmethod
    def _spec_changed(current: Specification, candidate: Specification) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in Specification.model_fields)

    @staticmethod
    def _spec_source_changed(current: SpecificationSourceRecord, candidate: SpecificationSourceRecord) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in SpecificationSourceRecord.model_fields)

    @staticmethod
    def _spec_version_changed(current: SpecificationVersion, candidate: SpecificationVersion) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in SpecificationVersion.model_fields)
