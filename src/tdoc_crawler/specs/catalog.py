"""Spec catalog operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from tdoc_crawler.models import SpecQueryFilters, SpecQueryResult
from tdoc_crawler.models.specs import Specification, SpecificationSourceRecord, SpecificationVersion

from .normalization import normalize_spec_number
from .sources.base import SpecSource

_logger = logging.getLogger(__name__)


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


class SpecCatalog:
    """Facade for spec metadata ingestion and queries."""

    def __init__(self, database: "TDocDatabase") -> None:
        self._database = database

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
                self._database.upsert_spec_source_record(record)
            self._database.upsert_specification(aggregated)
            for version in spec_versions:
                self._database.upsert_spec_version(version)

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

    def query_specs(self, filters: SpecQueryFilters, release: str) -> list[SpecQueryResult]:
        """Query stored spec metadata using the provided filters."""
        _ = release
        return self._database.query_specs(filters)
