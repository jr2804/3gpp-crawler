"""Spec database and crawling operations."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass

from tdoc_crawler.database.base import DocDatabase
from tdoc_crawler.database.errors import DatabaseError
from tdoc_crawler.database.oxyde_models import (
    Specification,
    SpecificationDownload,
    SpecificationSourceRecord,
    SpecificationVersion,
)
from tdoc_crawler.logging import get_logger
from tdoc_crawler.specs.models import SpecQueryFilters, SpecQueryResult
from tdoc_crawler.specs.sources.base import SpecSource
from tdoc_crawler.utils.normalization import normalize_release, normalize_spec_number
from tdoc_crawler.utils.parse import parse_spec_version, parse_spec_version_nbr

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
    async def upsert_specification(self, specification: Specification) -> tuple[bool, bool]:
        """Upsert a specification record."""
        existing = await self._get_specification(specification.spec_number)
        if existing is None:
            await Specification.objects.create(instance=specification)
            return True, False

        changed = self._spec_changed(existing, specification)
        await specification.save()
        return False, changed

    async def upsert_spec_source_record(self, record: SpecificationSourceRecord) -> tuple[bool, bool]:
        """Upsert a spec source record."""
        record_id = record.record_id or f"{record.spec_number}:{record.source_name}"
        updated_record = SpecificationSourceRecord(
            record_id=record_id,
            spec_number=record.spec_number,
            source_name=record.source_name,
            source_identifier=record.source_identifier,
            metadata_payload=record.metadata_payload,
            versions=record.versions,
            fetched_at=record.fetched_at,
        )
        existing = await self._get_spec_source_record(record_id)
        if existing is None:
            await SpecificationSourceRecord.objects.create(instance=updated_record)
            return True, False

        changed = self._spec_source_changed(existing, updated_record)
        await updated_record.save()
        return False, changed

    async def upsert_spec_version(self, version: SpecificationVersion) -> tuple[bool, bool]:
        """Upsert a spec version record."""
        record_id = version.record_id or f"{version.spec_number}:{version.version}:{version.source_name}"
        updated_version = SpecificationVersion(
            record_id=record_id,
            spec_number=version.spec_number,
            version=version.version,
            file_name=version.file_name,
            source_name=version.source_name,
        )
        existing = await self._get_spec_version(record_id)
        if existing is None:
            await SpecificationVersion.objects.create(instance=updated_version)
            return True, False

        changed = self._spec_version_changed(existing, updated_version)
        await updated_version.save()
        return False, changed

    async def clear_specs(self) -> dict[str, int]:
        """Clear all spec-related records from database.

        Returns:
            Mapping of table name to deleted row count.
        """
        return await self._clear_tables(
            [SpecificationDownload, SpecificationVersion, SpecificationSourceRecord, Specification]
        )

    async def crawl_specs(
        self,
        spec_numbers: list[str],
        release: str,
        sources: list[SpecSource],
    ) -> list[SpecCrawlResult]:
        """Crawl and store spec metadata for the provided spec numbers.

        Args:
            spec_numbers: Spec numbers to crawl.
            release: Release selector; use "latest" for newest version.
            sources: Spec metadata sources.

        Returns:
            List of crawl outcomes for each requested spec.
        """
        results: list[SpecCrawlResult] = []
        release_type, release_value, specificity = normalize_release(release)
        resolved_release = release_value if release_value is not None else ""
        resolved_specificity = specificity if specificity is not None else 0
        for raw_spec in spec_numbers:
            normalized = normalize_spec_number(raw_spec)
            compact = normalized.replace(".", "")
            results.append(
                await self._crawl_single_spec(
                    compact=compact,
                    normalized=normalized,
                    release=release,
                    release_type=release_type,
                    release_value=resolved_release,
                    specificity=resolved_specificity,
                    sources=sources,
                ),
            )
        return results

    @staticmethod
    async def get_spec_versions(spec_number: str) -> list[SpecificationVersion]:
        """Get all versions for a spec."""
        try:
            return await SpecificationVersion.objects.filter(spec_number=spec_number).all()
        except Exception as exc:
            _logger.exception("Failed to get spec versions for '%s': %s", spec_number, exc)
            msg = "spec-versions-read-failed"
            raise DatabaseError(msg, detail=str(exc)) from exc

    @staticmethod
    async def query_specs(filters: SpecQueryFilters) -> list[SpecQueryResult]:
        """Query stored spec metadata.

        Pushes spec_number, title, working_group, and status filters to
        SQL WHERE via Oxyde ORM. Source records are loaded only for matching
        specs.

        Args:
            filters: Filter criteria

        Returns:
            List of spec query results
        """
        qs = Specification.objects

        if filters.spec_numbers:
            allowed = [normalize_spec_number(value) for value in filters.spec_numbers]
            qs = qs.filter(spec_number__in=allowed)

        if filters.title:
            qs = qs.filter(title__icontains=filters.title.strip())

        if filters.working_group:
            qs = qs.filter(working_group__iexact=filters.working_group.strip())

        if filters.status:
            qs = qs.filter(status__iexact=filters.status.strip())

        specs = await qs.all()

        if not specs:
            return []

        spec_numbers = [spec.spec_number for spec in specs]
        source_records = await SpecificationSourceRecord.objects.filter(spec_number__in=spec_numbers).all()
        records_by_spec: dict[str, list[SpecificationSourceRecord]] = defaultdict(list)
        for record in source_records:
            records_by_spec[record.spec_number].append(record)

        return [
            SpecQueryResult(
                spec_number=spec.spec_number,
                title=spec.title,
                status=spec.status,
                working_group=spec.working_group,
                source_differences=_build_source_differences(records_by_spec.get(spec.spec_number, [])),
            )
            for spec in specs
        ]

    async def _crawl_single_spec(
        self,
        *,
        compact: str,
        normalized: str,
        release: str,
        release_type: str,
        release_value: str,
        specificity: int,
        sources: list[SpecSource],
    ) -> SpecCrawlResult:
        outcomes: list[SpecCrawlSourceOutcome] = []
        source_records: list[SpecificationSourceRecord] = []
        spec_versions: list[SpecificationVersion] = []
        aggregated: Specification | None = None

        # Fetch all sources in parallel (each does sync HTTP)
        fetch_tasks = [asyncio.to_thread(_process_source_fetch, src, normalized, compact) for src in sources]
        fetch_results = await asyncio.gather(*fetch_tasks)

        for source, result in zip(sources, fetch_results, strict=False):
            if result is None:
                outcomes.append(
                    SpecCrawlSourceOutcome(
                        source_name=source.name,
                        status="error",
                        versions=[],
                        message="fetch-failed",
                    ),
                )
                continue

            outcome, record, candidate, versions = result
            outcomes.append(outcome)
            source_records.append(record)
            aggregated = _aggregate_specs(aggregated, candidate)
            spec_versions.extend(versions)

        if not outcomes:
            return SpecCrawlResult(
                spec_number=normalized,
                release=release,
                status="error",
                latest_version=None,
                sources=[],
                message="no-sources",
            )

        threegpp_outcome = next((o for o in outcomes if o.source_name == "3gpp"), None)
        if threegpp_outcome is not None and threegpp_outcome.status == "error":
            _logger.warning("Skipping spec %s due to 3GPP source error", normalized)
            return SpecCrawlResult(
                spec_number=normalized,
                release=release,
                status="skipped",
                latest_version=None,
                sources=outcomes,
                message="3gpp-source-error",
            )

        if not _check_release_matches(outcomes, release_type, release_value, specificity):
            return SpecCrawlResult(
                spec_number=normalized,
                release=release,
                status="skipped",
                latest_version=aggregated.latest_version if aggregated else None,
                sources=outcomes,
                message="release-not-found",
            )

        if aggregated is None:
            return SpecCrawlResult(
                spec_number=normalized,
                release=release,
                status="error",
                latest_version=None,
                sources=outcomes,
                message="no-metadata",
            )

        for record in source_records:
            await self.upsert_spec_source_record(record)
        await self.upsert_specification(aggregated)
        for version in spec_versions:
            await self.upsert_spec_version(version)

        return SpecCrawlResult(
            spec_number=normalized,
            release=release,
            status="stored",
            latest_version=aggregated.latest_version,
            sources=outcomes,
        )

    async def _spec_table_rows(self) -> list[Specification]:
        return await self._table_rows(Specification)

    @staticmethod
    async def _get_specification(spec_number: str) -> Specification | None:
        return await Specification.objects.filter(spec_number=spec_number).first()

    @staticmethod
    async def _get_spec_source_record(record_id: str) -> SpecificationSourceRecord | None:
        try:
            return await SpecificationSourceRecord.objects.filter(record_id=record_id).first()
        except Exception as exc:
            _logger.exception("Failed to fetch spec source record '%s': %s", record_id, exc)
            msg = "spec-source-read-failed"
            raise DatabaseError(msg, detail=str(exc)) from exc

    @staticmethod
    async def _get_spec_version(record_id: str) -> SpecificationVersion | None:
        return await SpecificationVersion.objects.filter(record_id=record_id).first()

    @staticmethod
    def _spec_changed(current: Specification, candidate: Specification) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in Specification.model_fields)

    @staticmethod
    def _spec_source_changed(current: SpecificationSourceRecord, candidate: SpecificationSourceRecord) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in SpecificationSourceRecord.model_fields)

    @staticmethod
    def _spec_version_changed(current: SpecificationVersion, candidate: SpecificationVersion) -> bool:
        return any(getattr(current, field) != getattr(candidate, field) for field in SpecificationVersion.model_fields)


def _process_source_fetch(
    source: SpecSource,
    normalized: str,
    compact: str,
) -> tuple[SpecCrawlSourceOutcome, SpecificationSourceRecord | None, Specification | None, list[SpecificationVersion]] | None:
    """Process a single source fetch for a spec.

    Returns:
        Tuple of (outcome, source_record, candidate, versions), or None if fetch failed
        (in which case the error outcome is appended internally).
    """
    try:
        payload = source.fetch(normalized)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _logger.warning("Spec crawl failed for %s (%s): %s", normalized, source.name, exc)
        return None

    source_name = str(payload.get("source_name", source.name))
    source_identifier = payload.get("source_identifier")
    metadata_payload = payload.get("metadata_payload")
    if not isinstance(metadata_payload, dict):
        metadata_payload = {}

    versions = payload.get("versions")
    if not isinstance(versions, list):
        versions = []
    normalized_versions = [parse_spec_version_nbr(item) for item in versions]

    outcome = SpecCrawlSourceOutcome(
        source_name=source_name,
        status="ok",
        versions=normalized_versions,
    )

    source_record = SpecificationSourceRecord(
        record_id=f"{normalized}:{source_name}",
        spec_number=normalized,
        source_name=source_name,
        source_identifier=source_identifier if isinstance(source_identifier, str) else None,
        metadata_payload=metadata_payload,
        versions=normalized_versions,
    )

    candidate, versions_payload = _build_spec_candidate(
        compact=compact,
        metadata_payload=metadata_payload,
        normalized=normalized,
        source_name=source_name,
        versions=normalized_versions,
    )

    return outcome, source_record, candidate, versions_payload


def _build_spec_candidate(
    *,
    compact: str,
    metadata_payload: dict[str, object],
    normalized: str,
    source_name: str,
    versions: list[str],
) -> tuple[Specification, list[SpecificationVersion]]:
    title = str(metadata_payload.get("title", "Unknown"))
    spec_type = str(metadata_payload.get("spec_type", "TS"))
    status = str(metadata_payload.get("status", "unknown"))
    working_group = str(metadata_payload.get("working_group", "unknown"))
    series = str(metadata_payload.get("series", f"{normalized.split('.', maxsplit=1)[0]}_series"))
    latest_version = metadata_payload.get("latest_version")
    if latest_version is None and versions:
        latest_version = max(versions, key=parse_spec_version)

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
    spec_versions = _build_spec_versions(
        compact=compact,
        metadata_payload=metadata_payload,
        normalized=normalized,
        source_name=source_name,
        versions=versions,
    )
    return candidate, spec_versions


def _build_spec_versions(
    *,
    compact: str,
    metadata_payload: dict[str, object],
    normalized: str,
    source_name: str,
    versions: list[str],
) -> list[SpecificationVersion]:
    spec_versions: list[SpecificationVersion] = []
    for i, version in enumerate(versions):
        file_name = f"{compact}-unknown.zip"
        if "specfile" in metadata_payload and isinstance(metadata_payload["specfile"], list):
            spec_files = metadata_payload["specfile"]
            if i < len(spec_files):
                file_name = str(spec_files[i])
        elif "file_name" in metadata_payload:
            file_name = str(metadata_payload["file_name"])

        spec_versions.append(
            SpecificationVersion(
                record_id=f"{normalized}:{parse_spec_version_nbr(version)}:{source_name}",
                spec_number=normalized,
                version=parse_spec_version_nbr(version),
                file_name=file_name,
                source_name=source_name,
            ),
        )
    return spec_versions


def _aggregate_specs(current: Specification | None, candidate: Specification) -> Specification:
    """Merge candidate into current aggregated spec, preferring non-None latest_version."""
    if current is None:
        return candidate
    if current.latest_version is None and candidate.latest_version is not None:
        return Specification(
            spec_number=current.spec_number,
            spec_number_compact=current.spec_number_compact,
            spec_type=current.spec_type,
            title=current.title,
            status=current.status,
            working_group=current.working_group,
            series=current.series,
            latest_version=candidate.latest_version,
        )
    return current


def _apply_spec_filters(specs: list[Specification], filters: SpecQueryFilters) -> list[Specification]:
    """Apply filter criteria to a list of specs, returning filtered list."""
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

    return specs


def _build_source_differences(records: list[SpecificationSourceRecord]) -> dict[str, dict[str, str | None]]:
    """Compare metadata payloads across source records, returning fields that differ."""
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


def _check_release_matches(
    outcomes: list[SpecCrawlSourceOutcome],
    release_type: str,
    release_value: str,
    specificity: int,
) -> bool:
    """Check if any source outcome contains a version matching the release criteria."""
    if release_type in ("all", "latest"):
        return True
    if release_type in ("exact", "prefix"):
        return any(
            _version_matches_release(v, release_type, release_value, specificity)  # type: ignore[arg-type]
            for outcome in outcomes
            if outcome.status == "ok"
            for v in outcome.versions
        )
    return False


def _version_matches_release(version: str, release_type: str, release_value: str, specificity: int) -> bool:
    """Check if a version string matches the release selector."""
    try:
        v_parts = list(parse_spec_version(version).release)
    except (ValueError, TypeError, AttributeError) as exc:
        _logger.debug("Version parse failed for '%s': %s", version, exc)
        return False

    if release_type == "exact":
        return parse_spec_version_nbr(version) == parse_spec_version_nbr(release_value)

    # prefix match: check major (specificity=1) or major.minor (specificity=2)
    if len(v_parts) >= specificity:
        prefix_parts = release_value.split(".")
        return all(v_parts[i] == int(prefix_parts[i]) for i in range(specificity))

    return False
