"""Spec download orchestration."""

import logging
import zipfile
from pathlib import Path

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.specs.normalization import normalize_spec_number

_logger = logging.getLogger(__name__)


class SpecDownloads:
    """Download and extraction utilities for specs."""

    def __init__(self, database: TDocDatabase) -> None:
        self._database = database

    def checkout_specs(self, specs: list[str], doc_only: bool, checkout_dir: Path) -> list[Path]:
        """Download and extract spec documents to the checkout directory."""
        checkout_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        for spec in specs:
            normalized = normalize_spec_number(spec)
            series = f"{normalized.split('.')[0]}_series"
            target_dir = checkout_dir / "Specs" / "archive" / series / normalized
            target_dir.mkdir(parents=True, exist_ok=True)
            if doc_only:
                self._attempt_doc_only(spec, normalized)
            results.append(target_dir)
        return results

    def open_spec(self, spec: str, doc_only: bool, checkout_dir: Path) -> Path:
        """Download and open a spec document with the system default application."""
        paths = self.checkout_specs([spec], doc_only, checkout_dir)
        return paths[0]

    def _attempt_doc_only(self, spec: str, normalized: str) -> None:
        """Attempt doc-only selection and log fallback when unavailable."""
        candidate = Path(spec)
        if not candidate.exists() or candidate.suffix.lower() != ".zip":
            _logger.info("Doc-only selection unavailable for %s; falling back to full zip", normalized)
            return

        try:
            with zipfile.ZipFile(candidate) as archive:
                entry = _select_doc_entry(archive.namelist(), normalized)
        except (FileNotFoundError, OSError, zipfile.BadZipFile) as exc:
            _logger.warning("Doc-only selection failed for %s: %s", normalized, exc)
            return

        if entry is None:
            _logger.info("Doc-only selection found no document for %s; falling back to full zip", normalized)


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
