"""Spec download orchestration."""
import asyncio
import logging
import zipfile
from pathlib import Path

import requests
from zipinspect import HTTPZipReader

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.constants.urls import SPEC_URL_TEMPLATE
from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.http_client import download_to_file
from tdoc_crawler.specs.sources.base import SpecSource
from tdoc_crawler.utils.normalization import normalize_spec_number

_logger = logging.getLogger(__name__)


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
        results: list[Path] = []

        for spec in specs:
            url: str | None = None
            filename: str | None = None
            try:
                # check if it exists in the database; if not, attempt crawl if sources provided
                normalized = normalize_spec_number(spec)
                series = f"{normalized.split('.', maxsplit=1)[0]}_series"
                target_dir = checkout_dir / "Specs" / "archive" / series / normalized
                target_dir.mkdir(parents=True, exist_ok=True)

                # Resolve URL
                try:
                    url, filename = self._resolve_spec_url(spec, release)
                except ValueError:
                    if sources:
                        _logger.info("Spec metadata not found for %s, attempting crawl...", normalized)

                        self._database.crawl_specs([normalized], release, sources)

                        # Try again after crawl
                        try:
                            url, filename = self._resolve_spec_url(normalized, release)
                        except ValueError:
                            _logger.warning("Spec metadata still not found for %s after crawl", normalized)
                            continue
                    else:
                        _logger.warning("Spec metadata not found for %s and no sources provided", normalized)
                        continue

                if url is None or filename is None:
                    continue

                if sources:
                    _logger.info("Found URL: %s", url)

                # doc-only logic
                success = False
                if doc_only:
                    success = asyncio.run(self._attempt_doc_only_async(url, normalized, target_dir))

                if not success:
                    self._download_full_zip(url, target_dir / filename)
                    self._extract_zip(target_dir / filename, target_dir)

                results.append(target_dir)

            except Exception as exc:
                _logger.error("Failed to checkout %s: %s", spec, exc)
                continue

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

    def _resolve_spec_url(self, spec: str, release: str | None) -> tuple[str, str]:
        """Resolve spec number to download URL and filename."""
        release = release or "latest"
        normalized = normalize_spec_number(spec)
        series = f"{normalized.split('.', maxsplit=1)[0]}_series"
        versions = self._database.get_spec_versions(normalized)
        if not versions:
            raise ValueError(f"No versions found for spec {normalized}")

        # Sort versions to find latest. Version strings (e.g. 17.0.0) sort lexicographically okay for major.minor.patch
        # But 9.0.0 > 10.0.0 is False in string sort ('9' > '1').
        # We need generic version sort.
        # Simple tuple conversion:
        def parse_version(v: str) -> tuple[int, ...]:
            try:
                return tuple(map(int, v.split(".")))
            except ValueError:
                return (0,)

        versions.sort(key=lambda x: parse_version(x.version), reverse=True)

        # If specific release requested, filter versions by major version
        if release != "latest":
            try:
                release_major = int(release.split(".", maxsplit=1)[0])
                # Filter versions that match this major release
                filtered_versions = [v for v in versions if parse_version(v.version)[0] == release_major]
                if filtered_versions:
                    versions = filtered_versions
                else:
                    msg = f"No versions found for spec {normalized} with release {release}"
                    raise ValueError(msg)
            except (ValueError, IndexError) as e:
                msg = f"Invalid release format: {release}. Expected format like '17', '17.1', or '17.1.0'"
                raise ValueError(msg) from e

        target = versions[0]

        # Construct 3GPP FTP URL
        url = SPEC_URL_TEMPLATE.format(series=series, normalized=normalized, file_name=target.file_name)
        return url, target.file_name

    async def _attempt_doc_only_async(self, url: str, normalized: str, target_dir: Path) -> bool:
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

    def _download_full_zip(self, url: str, target_path: Path) -> None:
        """Download full zip file, re-use session if already created for doc-only attempt."""
        self.session = download_to_file(url, target_path, session=self.session, close_session=False, cache_manager_name=self._cache_manager.name)

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
