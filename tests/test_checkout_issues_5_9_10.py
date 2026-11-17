"""Regression tests for checkout robustness issues #5, #9 and #10.

- #9: empty / zero-member zip archives must be reported as errors.
- #10: archives published under a differing filename (trailing space, case)
  must be discoverable via the directory listing.
- #5: bulk checkout supports parallel workers while preserving input order.
"""

from __future__ import annotations

import io
import threading
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.tdocs.operations.checkout import (
    CheckoutResult,
    _resolve_corrected_url,
    checkout_tdoc,
    checkout_tdocs,
)


class TestEmptyArchive:
    """Issue #9: a zero-member / zero-byte archive must fail the checkout."""

    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_valid_empty_zip_raises(self, mock_download: Mock, checkout_dir: Path) -> None:
        mock_download.side_effect = lambda url, dest, session=None: dest.write_bytes(_zip_bytes())

        metadata = _metadata("S4-230645", "https://www.3gpp.org/ftp/S4-230645.zip")
        with pytest.raises(ValueError, match="contains no members"):
            checkout_tdoc(metadata, checkout_dir)

    @patch("tdoc_crawler.tdocs.operations.checkout._resolve_corrected_url")
    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_zero_byte_download_raises(self, mock_download: Mock, mock_resolve: Mock, checkout_dir: Path) -> None:
        mock_resolve.return_value = None
        mock_download.side_effect = lambda url, dest, session=None: dest.write_bytes(b"")

        metadata = _metadata("S4AA230110", "https://www.3gpp.org/ftp/S4AA230110.zip")
        with pytest.raises(ValueError, match="empty"):
            checkout_tdoc(metadata, checkout_dir)

    @patch("tdoc_crawler.tdocs.operations.checkout._resolve_corrected_url")
    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_empty_original_retries_corrected_url(self, mock_download: Mock, mock_resolve: Mock, checkout_dir: Path) -> None:
        """A 0-byte response triggers the corrected-URL retry, not just HTTPError/BadZipFile."""
        mock_resolve.return_value = "https://www.3gpp.org/ftp/S4aA230110.zip"
        calls = 0

        def download(url: str, dest: Path, session: object = None) -> None:
            nonlocal calls
            calls += 1
            dest.write_bytes(b"" if calls == 1 else _zip_bytes("doc.docx"))

        mock_download.side_effect = download
        metadata = _metadata("S4AA230110", "https://www.3gpp.org/ftp/S4AA230110.zip")
        result = checkout_tdoc(metadata, checkout_dir)

        assert calls == 2
        assert (result / "doc.docx").exists()


class TestCorrectedUrlMatching:
    """Issue #10: trailing-space and case-only filename variants are found."""

    def test_trailing_space_variant(self) -> None:
        result = self._run_resolve("S4-250486%20.zip", "S4-250486")
        assert result is not None
        assert result.endswith("S4-250486%20.zip")

    def test_case_variant(self) -> None:
        result = self._run_resolve("S4aA230110.zip", "S4AA230110")
        assert result is not None
        assert result.endswith("S4aA230110.zip")

    def _run_resolve(self, published: str, expected_id: str) -> str | None:
        html = f'<html><body><a href="{published}">{published}</a></body></html>'.encode()
        with patch("tdoc_crawler.tdocs.operations.checkout.requests.Session") as session_cls:
            response = Mock()
            response.content = html
            response.raise_for_status = Mock()
            session = Mock()
            session.get.return_value = response
            session_cls.return_value.__enter__ = Mock(return_value=session)
            session_cls.return_value.__exit__ = Mock(return_value=False)

            metadata = _metadata(
                expected_id,
                f"https://www.3gpp.org/ftp/Docs/{expected_id}.zip",
            )
            return _resolve_corrected_url(metadata)


class TestParallelCheckout:
    """Issue #5: bulk checkout runs downloads in parallel and stays ordered."""

    def test_workers_run_concurrently_and_preserve_order(self, checkout_dir: Path) -> None:
        barrier = threading.Barrier(3)
        started: list[str] = []
        lock = threading.Lock()

        def fake_checkout(metadata: TDocMetadata, dest: Path, **kwargs: object) -> Path:
            with lock:
                started.append(metadata.tdoc_id)
            barrier.wait(timeout=3)  # only succeeds if 3 run concurrently
            return dest / metadata.tdoc_id

        metas = [
            _metadata("S4-000001", "https://www.3gpp.org/ftp/S4-000001.zip"),
            _metadata("S4-000002", "https://www.3gpp.org/ftp/S4-000002.zip"),
            _metadata("S4-000003", "https://www.3gpp.org/ftp/S4-000003.zip"),
        ]

        with patch(
            "tdoc_crawler.tdocs.operations.checkout.checkout_tdoc",
            side_effect=fake_checkout,
        ):
            result = checkout_tdocs(metas, checkout_dir, workers=3)

        assert isinstance(result, CheckoutResult)
        assert result.success_count == 3
        assert result.error_count == 0
        assert sorted(started) == ["S4-000001", "S4-000002", "S4-000003"]

    def test_workers_defaults_to_sequential(self, checkout_dir: Path) -> None:
        metas = [_metadata("S4-000001", "https://www.3gpp.org/ftp/S4-000001.zip")]
        with patch(
            "tdoc_crawler.tdocs.operations.checkout.checkout_tdoc",
            return_value=checkout_dir / "S4-000001",
        ) as mock_checkout:
            result = checkout_tdocs(metas, checkout_dir)
        assert result.success_count == 1
        mock_checkout.assert_called_once()


def _metadata(tdoc_id: str, url: str) -> TDocMetadata:
    return TDocMetadata(
        tdoc_id=tdoc_id,
        url=url,
        title="Test",
        meeting_id=113,
        source="Test",
        contact="test@example.com",
        tdoc_type="Test Type",
        for_purpose="Test Purpose",
        agenda_item_nbr="1.0",
        agenda_item_text="Test Agenda Item",
        status="available",
        is_revision_of=None,
        file_size=None,
        date_created=None,
        validated=False,
        validation_failed=False,
    )


@pytest.fixture
def checkout_dir(tmp_path: Path) -> Path:
    return tmp_path / "checkout"


def _zip_bytes(*names: str) -> bytes:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as zf:
        for name in names:
            zf.writestr(name, "content")
    return content.getvalue()
