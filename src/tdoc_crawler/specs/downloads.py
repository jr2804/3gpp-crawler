"""Spec download orchestration."""

import asyncio
import logging
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from zipinspect import HTTPZipReader

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.specs.normalization import normalize_spec_number

if TYPE_CHECKING:
    from tdoc_crawler.specs.sources.base import SpecSource

_logger = logging.getLogger(__name__)


class SpecDownloads:
    """Download and extraction utilities for specs."""

    def __init__(self, database: TDocDatabase) -> None:
        self._database = database

    def checkout_specs(
        self,
        specs: list[str],
        doc_only: bool,
        checkout_dir: Path,
        release: str = "latest",
        sources: list[SpecSource] | None = None,
    ) -> list[Path]:
        """Download and extract spec documents to the checkout directory."""
        checkout_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []

        for spec in specs:
            try:
                normalized = normalize_spec_number(spec)
                series = f"{normalized.split('.')[0]}_series"
                target_dir = checkout_dir / "Specs" / "archive" / series / normalized
                target_dir.mkdir(parents=True, exist_ok=True)

                # Resolve URL
                try:
                    url, filename = self._resolve_spec_url(normalized, release)
                except ValueError as exc:
                    if sources:
                        _logger.info("Spec metadata not found for %s, attempting crawl...", normalized)
                        from tdoc_crawler.specs.catalog import SpecCatalog

                        catalog = SpecCatalog(self._database)
                        catalog.crawl_specs([normalized], release, sources)

                        # Try again after crawl
                        try:
                            url, filename = self._resolve_spec_url(normalized, release)
                        except ValueError:
                            _logger.warning("Spec metadata still not found for %s after crawl", normalized)
                            continue
                    else:
                        _logger.warning(exc)
                        continue

                # doc-only logic
                success = False
                if doc_only:
                    success = asyncio.run(self._attempt_doc_only_async(url, normalized, target_dir))

                if not success:
                    self._download_full_zip(url, target_dir / filename)
                    # Extract zip? Or just keep it?
                    # "Checkout" usually implies extraction or having files ready.
                    # 3GPP archive structure has zips.
                    # But if doc-only, we extract the doc.
                    # If full text, usually we keep the zip or extract it?
                    # Task says "Download, extract, and open".
                    # Existing implementations usually unzip TDocs.
                    # I will extract the zip if full download.
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

    def _resolve_spec_url(self, normalized: str, release: str) -> tuple[str, str]:
        """Resolve spec number to download URL and filename."""
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
                release_major = int(release.split(".")[0])
                # Filter versions that match this major release
                filtered_versions = [v for v in versions if parse_version(v.version)[0] == release_major]
                if filtered_versions:
                    versions = filtered_versions
                else:
                    msg = f"No versions found for spec {normalized} with release {release}"
                    raise ValueError(msg)
            except (ValueError, IndexError) as e:
                msg = f"Invalid release format: {release}. Expected format like '17' or '17.1'"
                raise ValueError(msg) from e

        target = versions[0]

        # Construct 3GPP FTP URL
        series = f"{normalized.split('.', maxsplit=1)[0]}_series"
        url = f"https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{target.file_name}"
        return url, target.file_name

    async def _attempt_doc_only_async(self, url: str, normalized: str, target_dir: Path) -> bool:
        """Attempt to download only the document file from remote zip."""
        try:
            async with HTTPZipReader(url) as reader:
                await reader.load_entries()
                # Find doc entry
                # HTTPZipReader entries likely have .filename or .name
                # I'll check first entry type
                entries: list[str] = [e.filename for e in reader.entries]
                doc_file = _select_doc_entry(entries, normalized)

                if not doc_file:
                    _logger.info("Doc-only: No document found in %s", url)
                    return False

                # Extract
                await reader.extract([e for e in reader.entries if e.filename == doc_file], out_dir=target_dir)
                return True
        except Exception as exc:
            _logger.warning("Doc-only download failed for %s: %s", url, exc)
            return False

    def _download_full_zip(self, url: str, target_path: Path) -> None:
        """Download full zip file."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        response = requests.get(url, stream=True, timeout=60, headers=headers)
        response.raise_for_status()
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def _extract_zip(self, zip_path: Path, extract_dir: Path) -> None:
        """Extract zip file."""
        try:
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(extract_dir)
        except Exception as exc:
            _logger.error("Failed to extract %s: %s", zip_path, exc)


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
