"""Spec download orchestration."""

import asyncio
import zipfile
from pathlib import Path
from typing import Any

import niquests as requests
from zipinspect import HTTPZipReader

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.constants.urls import SPEC_URL_TEMPLATE
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.http_client import download_to_file
from tdoc_crawler.logging import get_logger
from tdoc_crawler.specs.sources.base import SpecSource
from tdoc_crawler.utils.normalization import normalize_release, normalize_spec_number
from tdoc_crawler.utils.parse import parse_spec_version, parse_spec_version_nbr

_logger = get_logger(__name__)


class SpecDownloads:
    """Download and extraction utilities for specs."""

    def __init__(self, database: SpecDatabase, cache_manager_name: str | None = None) -> None:
        self._database = database
        self._cache_manager = resolve_cache_manager(cache_manager_name)
        self.session: requests.Session | None = None

    def __del__(self) -> None:
        if self.session:
            self.session.close()

    def checkout_specs(
        self,
        specs: list[str],
        doc_only: bool,
        checkout_dir: Path,
        release: str = "latest",
        sources: list[SpecSource] | None = None,
    ) -> list[Path]:
        """Download and extract spec documents to the checkout directory."""
        return asyncio.run(self.checkout_specs_async(specs, doc_only, checkout_dir, release, sources=sources))

    async def checkout_specs_async(
        self,
        specs: list[str],
        doc_only: bool,
        checkout_dir: Path,
        release: str = "latest",
        sources: list[SpecSource] | None = None,
    ) -> list[Path]:
        """Async variant of checkout_specs for async call paths."""
        results: list[Path] = []
        for spec in specs:
            target_dir = await self._checkout_single_spec(
                spec=spec,
                doc_only=doc_only,
                checkout_dir=checkout_dir,
                release=release,
                sources=sources,
            )
            if target_dir is not None:
                results.append(target_dir)

        return results

    def open_spec(
        self,
        spec: str,
        doc_only: bool,
        checkout_dir: Path,
        release: str = "latest",
        sources: list[SpecSource] | None = None,
    ) -> Path:
        """Download and open a spec document with the system default application."""
        paths = self.checkout_specs([spec], doc_only, checkout_dir, release, sources=sources)
        if not paths:
            raise FileNotFoundError(f"Spec {spec} could not be checked out")

        # Find the doc/valid file to open in the target dir
        target_dir = paths[0]
        # Look for .docx or .doc
        docs = list(target_dir.glob("*.doc*"))
        if docs:
            return docs[0]
        # Look for zip
        zips = list(target_dir.glob("*.zip"))
        if zips:
            return zips[0]
        return target_dir

    async def _checkout_single_spec(
        self,
        spec: str,
        doc_only: bool,
        checkout_dir: Path,
        release: str,
        sources: list[SpecSource] | None,
    ) -> Path | None:
        """Checkout a single spec into the archive and return target directory."""
        try:
            normalized = normalize_spec_number(spec)
            target_dir = self._build_target_dir(checkout_dir, normalized)

            resolved = await self._resolve_spec_url_with_fallback(spec, normalized, release, sources)
            if resolved is None:
                return None
            url, filename = resolved

            if sources:
                _logger.info("Found URL: %s", url)

            doc_only_success = False
            if doc_only:
                doc_only_success = await self._attempt_doc_only_async(url, normalized, target_dir)

            if not doc_only_success:
                self._download_full_zip(url, target_dir / filename)
                extract_subdir = target_dir / Path(filename).stem
                self._extract_zip(target_dir / filename, extract_subdir)
                return extract_subdir

            return target_dir
        except Exception as exc:
            _logger.error("Failed to checkout %s: %s", spec, exc)
            return None

    async def _resolve_spec_url_with_fallback(
        self,
        spec: str,
        normalized: str,
        release: str,
        sources: list[SpecSource] | None,
    ) -> tuple[str, str] | None:
        """Resolve spec URL, optionally crawling sources when metadata is missing."""
        try:
            return await self._resolve_spec_url(spec, release)
        except ValueError:
            if not sources:
                _logger.warning("Spec metadata not found for %s and no sources provided", normalized)
                return None

            _logger.info("Spec metadata not found for %s, attempting crawl...", normalized)
            await self._database.crawl_specs([normalized], release, sources)

            try:
                return await self._resolve_spec_url(normalized, release)
            except ValueError:
                _logger.warning("Spec metadata still not found for %s after crawl", normalized)
                return None

    async def _resolve_spec_url(self, spec: str, release: str | None) -> tuple[str, str]:
        """Resolve spec number to download URL and filename."""
        release = release or "latest"
        normalized = normalize_spec_number(spec)
        series = f"{normalized.split('.', maxsplit=1)[0]}_series"
        versions = await self._database.get_spec_versions(normalized)
        if not versions:
            raise ValueError(f"No versions found for spec {normalized}")

        versions.sort(key=lambda version: parse_spec_version(version.version), reverse=True)

        # If specific release requested, use normalize_release to handle various formats
        release_type, release_value, specificity = normalize_release(release)
        versions = self._filter_versions_by_release(
            versions=versions,
            release_type=release_type,
            release_value=release_value,
            specificity=specificity,
            normalized=normalized,
            release=release,
        )

        target = versions[0]

        # Construct 3GPP FTP URL
        url = SPEC_URL_TEMPLATE.format(series=series, normalized=normalized, file_name=target.file_name)
        return url, target.file_name

    def _download_full_zip(self, url: str, target_path: Path) -> None:
        """Download full zip file, re-use session if already created for doc-only attempt."""
        self.session = download_to_file(url, target_path, session=self.session, close_session=False, cache_manager_name=self._cache_manager.name)

    @staticmethod
    def _filter_versions_by_release(
        versions: list[Any],
        release_type: str,
        release_value: str,
        specificity: int,
        normalized: str,
        release: str,
    ) -> list[Any]:
        """Filter candidate versions by normalized release selector."""
        if release_type in {"latest", "all"}:
            return versions
        if release_type not in {"exact", "prefix"}:
            return versions

        filtered_versions: list[Any] = []
        for version_entry in versions:
            version_parts = parse_spec_version(version_entry.version).release
            if release_type == "exact":
                if parse_spec_version_nbr(version_entry.version) == parse_spec_version_nbr(release_value):
                    filtered_versions.append(version_entry)
                continue

            if len(version_parts) < specificity:
                continue
            prefix_parts = release_value.split(".")
            if all(version_parts[index] == int(prefix_parts[index]) for index in range(specificity)):
                filtered_versions.append(version_entry)

        if filtered_versions:
            return filtered_versions

        msg = f"No versions found for spec {normalized} with release {release}"
        raise ValueError(msg)

    @staticmethod
    def _build_target_dir(checkout_dir: Path, normalized: str) -> Path:
        """Create and return target checkout directory for one normalized spec."""
        series = f"{normalized.split('.', maxsplit=1)[0]}_series"
        target_dir = checkout_dir / "Specs" / "archive" / series / normalized
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @staticmethod
    async def _attempt_doc_only_async(url: str, normalized: str, target_dir: Path) -> bool:
        """Attempt to download only the document file from remote zip."""
        try:
            async with HTTPZipReader(url) as reader:
                # entries is populated by __aenter__ via load_entries()
                # Find doc entry using .path (not .filename)
                entries = reader.entries
                if entries is None:
                    _logger.info("Doc-only: No entries found in %s", url)
                    return False

                doc_file = _select_doc_entry([e.path for e in entries], normalized)

                if not doc_file:
                    _logger.info("Doc-only: No document found in %s", url)
                    return False

                # Extract matching entries to target_dir
                for entry in entries:
                    if entry.path == doc_file:
                        target_path = target_dir / doc_file.split("/")[-1]
                        with target_path.open("wb") as f:
                            async for _ in reader.extract(entry, f):
                                pass
                        return True
                return False
        except Exception as exc:
            _logger.warning("Doc-only download failed for %s: %s", url, exc)
            return False

    @staticmethod
    def _extract_zip(zip_file: Path, extract_dir: Path, keep_zip: bool = True) -> None:
        """Extract zip file."""
        try:
            with zipfile.ZipFile(zip_file) as z:
                z.extractall(extract_dir)

            if not keep_zip:
                zip_file.unlink()
        except Exception as exc:
            _logger.error("Failed to extract %s: %s", zip_file, exc)


def _select_doc_entry(entries: list[str], normalized: str) -> str | None:
    compact = normalized.replace(".", "")
    for entry in entries:
        lower = entry.lower()
        if not (lower.endswith(".doc") or lower.endswith(".docx")):
            continue
        token = lower.replace(".", "")
        if compact.lower() in token:
            return entry
    return None
