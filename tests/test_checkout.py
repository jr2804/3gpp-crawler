"""Tests for TDoc checkout functionality."""

import io
import os
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pathspec import GitIgnoreSpec

from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.tdocs.models import TDocStatus
from tdoc_crawler.tdocs.operations.checkout import (
    _resolve_corrected_url,
    _select_main_file,
    checkout_tdoc,
    get_checked_out_tdocs,
    get_checkout_path,
    prepare_tdoc_file,
    resolve_tdoc_checkout_path,
)
from tdoc_crawler.utils import clutter
from tdoc_crawler.utils.security import safe_extract_zip


class TestGetCheckoutPath:
    """Tests for get_checkout_path function."""

    def test_standard_url(self, sample_tdoc_metadata: TDocMetadata, checkout_dir: Path) -> None:
        """Test checkout path calculation for standard 3GPP URL."""
        path = get_checkout_path(sample_tdoc_metadata, checkout_dir)
        expected = checkout_dir / "tsg_sa" / "SA4" / "S4-251234"
        assert path == expected

    def test_url_with_meeting_in_path(self, checkout_dir: Path) -> None:
        """Test checkout path for URL with meeting in path."""
        metadata = TDocMetadata(
            tdoc_id="R1-2301234",
            url="https://www.3gpp.org/ftp/tsg_ran/RAN1/r1-2301234.zip",
            title="Test",
            meeting_id=123,
            source="Test",
            contact="test@example.com",
            tdoc_type="Test Type",
            for_purpose="Test Purpose",
            agenda_item_nbr="1.0",
            agenda_item_text="Test Agenda Item",
            status="available",
            meeting_name="Test Meeting",
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )
        path = get_checkout_path(metadata, checkout_dir)
        expected = checkout_dir / "tsg_ran" / "RAN1" / "R1-2301234"
        assert path == expected

    def test_url_without_ftp_in_path(self, checkout_dir: Path) -> None:
        """Test checkout path for URL without 'ftp' component."""
        metadata = TDocMetadata(
            tdoc_id="S4-251234",
            url="some/path/s4-251234.zip",
            title="Test",
            meeting_id=113,
            source="Test",
            contact="test@example.com",
            tdoc_type="Test Type",
            for_purpose="Test Purpose",
            agenda_item_nbr="1.0",
            agenda_item_text="Test Agenda Item",
            status="available",
            meeting_name="Test Meeting",
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )
        path = get_checkout_path(metadata, checkout_dir)
        expected = checkout_dir / "some" / "path" / "S4-251234"
        assert path == expected


class TestCheckoutTDoc:
    """Tests for checkout_tdoc function."""

    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_successful_checkout(
        self,
        mock_download_to_file: Mock,
        sample_tdoc_metadata: TDocMetadata,
        checkout_dir: Path,
    ) -> None:
        """Test successful TDoc checkout."""
        checkout_path = get_checkout_path(sample_tdoc_metadata, checkout_dir)

        # Create a mock zip file
        def mock_download(url: str, destination: Path, session: object = None) -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = io.BytesIO()
            with zipfile.ZipFile(content, "w") as zf:
                zf.writestr("test.txt", "test content")
            destination.write_bytes(content.getvalue())

        mock_download_to_file.side_effect = mock_download

        result = checkout_tdoc(sample_tdoc_metadata, checkout_dir)

        assert result == checkout_path
        assert result.exists()
        assert (result / "test.txt").exists()
        assert not (result / "S4-251234.zip").exists()  # Zip should be cleaned up

    def test_already_checked_out(
        self,
        sample_tdoc_metadata: TDocMetadata,
        checkout_dir: Path,
    ) -> None:
        """Test that already checked out TDoc is skipped."""
        checkout_path = get_checkout_path(sample_tdoc_metadata, checkout_dir)
        checkout_path.mkdir(parents=True)
        (checkout_path / "existing.txt").write_text("existing")

        result = checkout_tdoc(sample_tdoc_metadata, checkout_dir)

        assert result == checkout_path

    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_force_recheckout(
        self,
        mock_download_to_file: Mock,
        sample_tdoc_metadata: TDocMetadata,
        checkout_dir: Path,
    ) -> None:
        """Test force option re-downloads existing TDoc."""
        checkout_path = get_checkout_path(sample_tdoc_metadata, checkout_dir)
        checkout_path.mkdir(parents=True)

        # Create a mock zip file
        def mock_download(url: str, destination: Path, session: object = None) -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = io.BytesIO()
            with zipfile.ZipFile(content, "w") as zf:
                zf.writestr("new.txt", "new content")
            destination.write_bytes(content.getvalue())

        mock_download_to_file.side_effect = mock_download

        result = checkout_tdoc(sample_tdoc_metadata, checkout_dir, force=True)

        assert result == checkout_path
        mock_download_to_file.assert_called_once()

    def test_invalid_url_scheme(self, checkout_dir: Path) -> None:
        """Test that invalid URL scheme raises ValueError."""
        metadata = TDocMetadata(
            tdoc_id="S4-251234",
            url="file:///local/path/s4-251234.zip",
            title="Test",
            meeting_id=113,
            source="Test",
            contact="test@example.com",
            tdoc_type="Test Type",
            for_purpose="Test Purpose",
            agenda_item_nbr="1.0",
            agenda_item_text="Test Agenda Item",
            status="available",
            meeting_name="Test Meeting",
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )

        with pytest.raises(ValueError, match="unsupported-url-scheme"):
            checkout_tdoc(metadata, checkout_dir)

    @patch("tdoc_crawler.tdocs.operations.checkout._resolve_corrected_url")
    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_case_correct_fallback_on_bad_zip(
        self,
        mock_download_to_file: Mock,
        mock_resolve_url: Mock,
        sample_tdoc_metadata: TDocMetadata,
        checkout_dir: Path,
    ) -> None:
        """Test that checkout retries with case-correct URL when first download is invalid."""
        corrected_url = "https://www.3gpp.org/ftp/tsg_sa/SA4/S4-251234.zip"
        mock_resolve_url.return_value = corrected_url

        call_count = 0

        def mock_download(url: str, destination: Path, session: object = None) -> None:
            nonlocal call_count
            call_count += 1
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = io.BytesIO()
            if call_count == 1:
                # First call: invalid/empty zip
                destination.write_bytes(b"not-a-zip")
            else:
                # Second call: valid zip
                with zipfile.ZipFile(content, "w") as zf:
                    zf.writestr("doc.txt", "document content")
                destination.write_bytes(content.getvalue())

        mock_download_to_file.side_effect = mock_download

        result = checkout_tdoc(sample_tdoc_metadata, checkout_dir)

        assert result == get_checkout_path(sample_tdoc_metadata, checkout_dir)
        assert (result / "doc.txt").exists()
        assert call_count == 2
        mock_resolve_url.assert_called_once()

    @patch("tdoc_crawler.tdocs.operations.checkout._resolve_corrected_url")
    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_fallback_propagates_when_no_corrected_url(
        self,
        mock_download_to_file: Mock,
        mock_resolve_url: Mock,
        sample_tdoc_metadata: TDocMetadata,
        checkout_dir: Path,
    ) -> None:
        """Test that BadZipFile is re-raised when no case-correct URL is found."""
        mock_resolve_url.return_value = None

        def mock_download(url: str, destination: Path, session: object = None) -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"not-a-zip")

        mock_download_to_file.side_effect = mock_download

        with pytest.raises(zipfile.BadZipFile):
            checkout_tdoc(sample_tdoc_metadata, checkout_dir)


class TestResolveCorrectedUrl:
    """Tests for _resolve_corrected_url function."""

    @patch("tdoc_crawler.tdocs.operations.checkout.requests.Session")
    def test_finds_case_insensitive_match(self, mock_session_cls: Mock) -> None:
        """Test that function finds a case-insensitive filename match in directory listing."""
        mock_response = Mock()
        mock_response.content = b"""
        <html><body>
        <a href="S4aA230110.zip">S4aA230110.zip</a>
        <a href="OTHER.zip">OTHER.zip</a>
        </body></html>
        """
        mock_response.raise_for_status = Mock()
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = Mock(return_value=False)

        metadata = TDocMetadata(
            tdoc_id="S4AA230110",
            url="https://www.3gpp.org/ftp/TSG_SA/WG4_CODEC/Docs/S4AA230110.zip",
            title="Test",
            meeting_id=123,
            source="Test",
            contact="test@example.com",
            tdoc_type="Test Type",
            for_purpose="Test Purpose",
            agenda_item_nbr="1.0",
            agenda_item_text="Test Agenda Item",
            status="available",
            meeting_name="Test Meeting",
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )

        result = _resolve_corrected_url(metadata)

        assert result == "https://www.3gpp.org/ftp/TSG_SA/WG4_CODEC/Docs/S4aA230110.zip"
        mock_session.get.assert_called_once_with(
            "https://www.3gpp.org/ftp/TSG_SA/WG4_CODEC/Docs/",
            timeout=60,
        )

    @patch("tdoc_crawler.tdocs.operations.checkout.requests.Session")
    def test_returns_none_when_no_match(self, mock_session_cls: Mock) -> None:
        """Test that function returns None when no case-insensitive match exists."""
        mock_response = Mock()
        mock_response.content = b"<html><body><a href='OTHER.zip'>OTHER.zip</a></body></html>"
        mock_response.raise_for_status = Mock()
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = Mock(return_value=False)

        metadata = TDocMetadata(
            tdoc_id="S4AA230110",
            url="https://www.3gpp.org/ftp/TSG_SA/WG4_CODEC/Docs/S4AA230110.zip",
            title="Test",
            meeting_id=123,
            source="Test",
            contact="test@example.com",
            tdoc_type="Test Type",
            for_purpose="Test Purpose",
            agenda_item_nbr="1.0",
            agenda_item_text="Test Agenda Item",
            status="available",
            meeting_name="Test Meeting",
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )

        result = _resolve_corrected_url(metadata)

        assert result is None

    @patch("tdoc_crawler.tdocs.operations.checkout.requests.Session")
    def test_returns_none_on_request_error(self, mock_session_cls: Mock) -> None:
        """Test that function returns None when directory listing request fails."""
        mock_session = Mock()
        mock_session.get.side_effect = ConnectionError("network error")
        mock_session_cls.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = Mock(return_value=False)

        metadata = TDocMetadata(
            tdoc_id="S4AA230110",
            url="https://www.3gpp.org/ftp/TSG_SA/WG4_CODEC/Docs/S4AA230110.zip",
            title="Test",
            meeting_id=123,
            source="Test",
            contact="test@example.com",
            tdoc_type="Test Type",
            for_purpose="Test Purpose",
            agenda_item_nbr="1.0",
            agenda_item_text="Test Agenda Item",
            status="available",
            meeting_name="Test Meeting",
            is_revision_of=None,
            file_size=None,
            date_created=None,
            validated=False,
            validation_failed=False,
        )

        result = _resolve_corrected_url(metadata)

        assert result is None


class TestGetCheckedOutTdocs:
    """Tests for get_checked_out_tdocs function."""

    def test_empty_checkout_dir(self, checkout_dir: Path) -> None:
        """Test empty checkout directory returns empty list."""
        result = get_checked_out_tdocs(checkout_dir)
        assert result == []

    def test_nonexistent_checkout_dir(self, tmp_path: Path) -> None:
        """Test non-existent checkout directory returns empty list."""
        result = get_checked_out_tdocs(tmp_path / "nonexistent")
        assert result == []

    def test_checked_out_tdocs(self, checkout_dir: Path) -> None:
        """Test finding checked out TDocs."""
        # Create some checked out TDoc directories
        (checkout_dir / "tsg_sa" / "SA4" / "S4-251234").mkdir(parents=True)
        (checkout_dir / "tsg_sa" / "SA4" / "S4-251234" / "file.txt").write_text("content")

        (checkout_dir / "tsg_ran" / "RAN1" / "R1-2301234").mkdir(parents=True)
        (checkout_dir / "tsg_ran" / "RAN1" / "R1-2301234" / "doc.txt").write_text("content")

        result = get_checked_out_tdocs(checkout_dir)

        assert sorted(result) == ["R1-2301234", "S4-251234"]


class TestResolveTdocCheckoutPath:
    """Tests for resolve_tdoc_checkout_path function."""

    def test_finds_tdoc_in_nested_docs_structure(self, tmp_path: Path) -> None:
        """Test resolve_tdoc_checkout_path finds TDoc in 3GPP FTP hierarchy."""
        checkout_base = tmp_path / "checkout"

        # Create realistic 3GPP FTP structure
        tdoc_path = checkout_base / "TSG_SA" / "WG4_CODEC" / "TSGS4_131-bis-e" / "Docs" / "S4-250638"
        tdoc_path.mkdir(parents=True)
        (tdoc_path / "S4-250638.docx").write_text("content")

        result = resolve_tdoc_checkout_path("S4-250638", checkout_base)
        assert result == tdoc_path

    def test_finds_tdoc_in_ran_structure(self, tmp_path: Path) -> None:
        """Test resolve_tdoc_checkout_path finds TDoc in RAN hierarchy."""
        checkout_base = tmp_path / "checkout"

        # Create RAN structure
        tdoc_path = checkout_base / "TSG_RAN" / "WG1_RH" / "TSGR1_115" / "Docs" / "R1-2300001"
        tdoc_path.mkdir(parents=True)
        (tdoc_path / "R1-2300001.pdf").write_text("content")

        result = resolve_tdoc_checkout_path("R1-2300001", checkout_base)
        assert result == tdoc_path

    def test_returns_none_for_nonexistent_tdoc(self, tmp_path: Path) -> None:
        """Test resolve_tdoc_checkout_path returns None when TDoc not found."""
        checkout_base = tmp_path / "checkout"
        checkout_base.mkdir(parents=True)

        result = resolve_tdoc_checkout_path("S4-999999", checkout_base)
        assert result is None


class TestSelectMainFile:
    """Tests for _select_main_file: picks the right file by type, not by name antipatterns."""

    def test_picks_real_docx_over_macos_clutter(self, tmp_path: Path) -> None:
        """The real .docx wins over __MACOSX/._* sidecars because suffix matches."""
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        macos = extract_dir / "__MACOSX"
        macos.mkdir()
        (macos / "._S4-261599 real.docx").write_bytes(b"clutter")
        (extract_dir / "S4-261599 real.docx").write_bytes(b"real")

        chosen = _select_main_file(extract_dir, "S4-261599")
        assert chosen.name == "S4-261599 real.docx"
        assert not chosen.parts[-2].startswith("_")

    def test_unknown_suffix_files_are_not_picked_over_known_documents(self, tmp_path: Path) -> None:
        """A .docx is preferred over a .png / .xml even if those are bigger."""
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "metadata.xml").write_bytes(b"x" * 10_000)
        (extract_dir / "cover.png").write_bytes(b"x" * 5_000)
        (extract_dir / "S4-261599 notes.docx").write_bytes(b"x" * 100)

        chosen = _select_main_file(extract_dir, "S4-261599")
        assert chosen.suffix == ".docx"

    def test_later_mtime_wins_among_same_suffix_documents(self, tmp_path: Path) -> None:
        """Same suffix, no TDoc prefix: the more recently modified file wins (size is not ranked)."""
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        older = extract_dir / "small.docx"
        newer = extract_dir / "big.docx"
        older.write_bytes(b"x")
        newer.write_bytes(b"x" * 1000)
        os.utime(older, (1_000_000_000, 1_000_000_000))
        os.utime(newer, (2_000_000_000, 2_000_000_000))

        chosen = _select_main_file(extract_dir, "S4-261599")
        assert chosen.name == "big.docx"

    def test_pdf_is_treated_as_a_document(self, tmp_path: Path) -> None:
        """3GPP also serves loose PDFs; a .pdf must be pickable."""
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "S4-261599 paper.pdf").write_bytes(b"%PDF-1.4")

        chosen = _select_main_file(extract_dir, "S4-261599")
        assert chosen.suffix == ".pdf"

    def test_tdoc_id_prefix_wins_among_documents(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "cover.png").write_bytes(b"x" * 100)
        (extract_dir / "S4-261599 on binaural capture.docx").write_bytes(b"x" * 50)

        chosen = _select_main_file(extract_dir, "S4-261599")
        assert chosen.name.startswith("S4-261599 ")

    def test_only_clutter_in_archive_falls_back_to_largest(self, tmp_path: Path) -> None:
        """If the zip contains only non-document files, pick the largest by suffix
        fallback (not by name). Documents always take precedence; only when
        there are zero documents do we fall back to a size-based pick of
        whatever's there. This is a useful last-ditch signal -- the alternative
        is to raise, which would block an open() over a real archive that just
        doesn't happen to have an Office file in it.
        """
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "_notes.txt").write_bytes(b"x")
        (extract_dir / "ghost.xml").write_bytes(b"x" * 1000)

        chosen = _select_main_file(extract_dir, "S4-261599")
        assert chosen.name == "ghost.xml"

    def test_no_files_raises(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="no-files-in-archive"):
            _select_main_file(extract_dir, "S4-261599")

    def test_exact_id_name_wins(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "S4-261599 On objective evaluation.docx").write_bytes(b"x")
        (extract_dir / "S4-261599.docx").write_bytes(b"x")

        chosen = _select_main_file(extract_dir, "S4-261599")

        assert chosen.name == "S4-261599.docx"

    def test_title_match_outranks_other_prefixed_files(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        main = extract_dir / "S4-261599 On objective evaluation of binaural capture.docx"
        main.write_bytes(b"x")
        (extract_dir / "S4-261599 Annex A test data.xlsx").write_bytes(b"x" * 500)

        chosen = _select_main_file(extract_dir, "S4-261599", title="On objective evaluation of binaural capture")

        assert chosen == main

    def test_case_insensitive_prefix(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "Presentation.pptx").write_bytes(b"x" * 900)
        (extract_dir / "s4-261599 proposal.pptx").write_bytes(b"x")

        chosen = _select_main_file(extract_dir, "S4-261599")

        assert chosen.name == "s4-261599 proposal.pptx"

    @pytest.mark.parametrize(
        ("better", "worse"),
        [
            (".docx", ".pptx"),
            (".pptx", ".ppt"),
            (".ppt", ".pdf"),
            (".pdf", ".xlsx"),
            (".xlsx", ".doc"),
            (".doc", ".xls"),
        ],
    )
    def test_type_preference_order(self, tmp_path: Path, better: str, worse: str) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / f"S4-261599 title{better}").write_bytes(b"x")
        (extract_dir / f"S4-261599 title{worse}").write_bytes(b"x")

        chosen = _select_main_file(extract_dir, "S4-261599")

        assert chosen.name == f"S4-261599 title{better}"

    def test_marked_version_wins_by_content(self, tmp_path: Path) -> None:
        """S4-242060 shape: v2 carries marks, v2_clean is the export."""
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        marked = extract_dir / "S4-242060_ATIAS_subjective_test_method_v2.docx"
        _write_docx(marked, marked=True)
        clean = extract_dir / "S4-242060_ATIAS_subjective_test_method_v2_clean.docx"
        _write_docx(clean, marked=False)
        chosen = _select_main_file(extract_dir, "S4-242060")
        assert chosen == marked

    def test_marked_wins_regardless_of_filename(self, tmp_path: Path) -> None:
        """No filename convention: the file whose *content* has revision marks
        wins even when its name suggests otherwise ("_clean").
        """
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        clean = extract_dir / "S4-242060_ATIAS_subjective_test_method_v2.docx"
        _write_docx(clean, marked=False)
        marked = extract_dir / "S4-242060_ATIAS_subjective_test_method_v2_clean.docx"
        _write_docx(marked, marked=True)
        chosen = _select_main_file(extract_dir, "S4-242060")
        assert chosen == marked

    def test_unmarked_pair_falls_back_to_newest_mtime(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        older = extract_dir / "S4-242060 title v2.docx"
        _write_docx(older, marked=False)
        newer = extract_dir / "S4-242060 title v3 clean.docx"
        _write_docx(newer, marked=False)
        os.utime(older, (1_000_000_000, 1_000_000_000))
        os.utime(newer, (2_000_000_000, 2_000_000_000))
        chosen = _select_main_file(extract_dir, "S4-242060")
        assert chosen == newer

    def test_corrupt_docx_counts_as_unmarked(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        (extract_dir / "S4-242060 title.docx").write_bytes(b"not a zip")
        marked = extract_dir / "S4-242060 title other.docx"
        _write_docx(marked, marked=True)
        chosen = _select_main_file(extract_dir, "S4-242060")
        assert chosen == marked


class TestPrepareTDocFile:
    """Tests for prepare_tdoc_file: shared layout with checkout_tdoc."""

    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_zip_uses_meeting_mirror_path(
        self,
        mock_download: Mock,
        checkout_dir: Path,
        tmp_path: Path,
    ) -> None:
        """prepare_tdoc_file must lay out zips under the same mirror path as checkout_tdoc.
        The macOS sidecar is dropped at extraction (AppleDouble magic), so only the
        real document exists on disk and is picked.
        """
        tdoc_id = "S4-261599"
        url = "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/S4-261599.zip"
        metadata = _make_metadata(tdoc_id, url)

        zip_path = tmp_path / "S4-261599.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("__MACOSX/._S4-261599 On binaural capture.docx", b"\x00\x05\x16\x07" + b"x" * 1000)
            zf.writestr(f"{tdoc_id} On binaural capture.docx", b"real")

        def _write_zip(url: str, dest: Path, session: object = None) -> None:
            dest.write_bytes(zip_path.read_bytes())

        mock_download.side_effect = _write_zip

        result = prepare_tdoc_file(metadata, checkout_dir)

        expected_dir = checkout_dir / "tsg_sa" / "WG4_CODEC" / "TSGS4_137-e" / "Docs" / tdoc_id
        assert result.parent == expected_dir
        assert result.name == f"{tdoc_id} On binaural capture.docx"
        assert not (expected_dir / "__MACOSX").exists()

    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_zip_return_dir_returns_extract_dir(
        self,
        mock_download: Mock,
        checkout_dir: Path,
        tmp_path: Path,
    ) -> None:
        tdoc_id = "S4-261600"
        url = f"https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/{tdoc_id}.zip"
        metadata = _make_metadata(tdoc_id, url)

        zip_path = tmp_path / f"{tdoc_id}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(f"{tdoc_id} doc.docx", b"x")

        mock_download.side_effect = lambda u, d, session=None: d.write_bytes(zip_path.read_bytes())

        result = prepare_tdoc_file(metadata, checkout_dir, return_dir=True)
        expected_dir = checkout_dir / "tsg_sa" / "WG4_CODEC" / "TSGS4_137-e" / "Docs" / tdoc_id
        assert result == expected_dir

    def test_withdrawn_raises(self, checkout_dir: Path) -> None:
        metadata = _make_metadata(
            "S4-261601",
            "https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/S4-261601.zip",
            status=TDocStatus.WITHDRAWN,
        )
        with pytest.raises(FileNotFoundError, match="withdrawn"):
            prepare_tdoc_file(metadata, checkout_dir)

    def test_missing_url_raises(self, checkout_dir: Path) -> None:
        metadata = _make_metadata("S4-261602", None)
        with pytest.raises(ValueError, match="URL is None"):
            prepare_tdoc_file(metadata, checkout_dir)

    @patch("tdoc_crawler.tdocs.operations.checkout.download_to_file")
    def test_non_zip_uses_mirror_path(
        self,
        mock_download: Mock,
        checkout_dir: Path,
    ) -> None:
        """Non-zip TDocs (e.g. a loose .docx) also live under the mirror path."""
        tdoc_id = "S4-261603"
        url = f"https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_137-e/Docs/{tdoc_id}.docx"
        metadata = _make_metadata(tdoc_id, url)
        mock_download.side_effect = lambda u, d, session=None: d.write_bytes(b"x")

        result = prepare_tdoc_file(metadata, checkout_dir)
        expected_dir = checkout_dir / "tsg_sa" / "WG4_CODEC" / "TSGS4_137-e" / "Docs" / tdoc_id
        assert result.parent == expected_dir
        assert result.name == f"{tdoc_id}.docx"


class TestSafeExtractZipPathTraversal:
    """Tests that safe_extract_zip's security job is path-traversal protection."""

    def test_rejects_zip_slip(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../escaped.txt", b"x")
            zf.writestr("inside.txt", b"y")

        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="escapes target directory"):
            safe_extract_zip(zip_path, out)


class TestSafeExtractZipClutterIgnore:
    """safe_extract_zip drops clutter per the gitignore-style pattern file."""

    def test_drops_default_clutter_patterns(self, tmp_path: Path) -> None:
        """The shipped defaults drop macOS/Windows/Office metadata."""
        with zipfile.ZipFile(tmp_path / "src.zip", "w") as zf:
            zf.writestr("__MACOSX/._real.docx", b"x" * 10)
            zf.writestr("._real.docx", b"x" * 10)
            zf.writestr("sub/.DS_Store", b"ds")
            zf.writestr("Thumbs.db", b"t")
            zf.writestr("~$real.docx", b"lock")
            zf.writestr("real.docx", b"real")

        out = self._extract(tmp_path)

        assert (out / "real.docx").exists()
        assert not (out / "__MACOSX").exists()
        assert not any(out.rglob("._*"))
        assert not any(out.rglob(".DS_Store"))
        assert not (out / "Thumbs.db").exists()
        assert not any(out.rglob("~$*"))

    def test_user_patterns_extend_filtering(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A user clutter-ignore file adds patterns; ``!`` re-includes."""
        ignore_file = tmp_path / "clutter-ignore"
        ignore_file.write_text("*.png\n!keep.png\n", encoding="utf-8")
        monkeypatch.setattr(clutter, "get_clutter_spec", lambda: GitIgnoreSpec.from_lines(["*.png", "!keep.png"]))
        with zipfile.ZipFile(tmp_path / "src.zip", "w") as zf:
            zf.writestr("cover.png", b"x")
            zf.writestr("keep.png", b"x")
            zf.writestr("real.docx", b"real")

        out = self._extract(tmp_path)

        assert (out / "keep.png").exists()
        assert (out / "real.docx").exists()
        assert not (out / "cover.png").exists()

    def test_user_ignore_file_materialized_from_default(self, tmp_path: Path) -> None:
        """user_ignore_file() writes the packaged defaults into the cache dir."""
        target = clutter.user_ignore_file(tmp_path)

        assert target == tmp_path / clutter.USER_IGNORE_FILENAME
        assert target.exists()
        assert GitIgnoreSpec.from_lines(target.read_text(encoding="utf-8").splitlines()).match_file("__MACOSX/._x")

    def _extract(self, tmp_path: Path) -> Path:
        out = tmp_path / "out"
        out.mkdir()
        safe_extract_zip(tmp_path / "src.zip", out)
        return out


class TestSelectMainFileIgnoresLegacyClutter:
    """_select_main_file skips clutter even in pre-existing checkout dirs."""

    def test_legacy_macos_dir_on_disk_is_skipped(self, tmp_path: Path) -> None:
        """Old checkouts contain __MACOSX dirs on disk; the picker must skip them."""
        extract_dir = tmp_path / "extracted"
        macos = extract_dir / "__MACOSX"
        macos.mkdir(parents=True)
        # Sidecar is bigger and also .docx — must not win.
        (macos / "._S4-261599 big.docx").write_bytes(b"x" * 10_000)
        (extract_dir / "S4-261599 real.docx").write_bytes(b"x" * 100)

        chosen = _select_main_file(extract_dir, "S4-261599")

        assert chosen.name == "S4-261599 real.docx"

    def test_only_clutter_on_disk_raises(self, tmp_path: Path) -> None:
        extract_dir = tmp_path / "extracted"
        macos = extract_dir / "__MACOSX"
        macos.mkdir(parents=True)
        (macos / "._S4-261599.docx").write_bytes(b"x")

        with pytest.raises(FileNotFoundError, match="no-files-in-archive"):
            _select_main_file(extract_dir, "S4-261599")


@pytest.fixture(autouse=True)
def _pin_clutter_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin clutter filtering to the shipped defaults so tests are hermetic
    regardless of any clutter-ignore file in the machine's cache dir.
    """
    monkeypatch.setattr(clutter, "get_clutter_spec", clutter.packaged_default_spec)


def _write_docx(path: Path, *, marked: bool, text: str = "body") -> None:
    """Write a minimal .docx zip; *marked* injects tracked-change elements."""
    revision = '<w:ins w:id="1" w:author="t"><w:r><w:t>edit</w:t></w:r></w:ins>' if marked else ""
    document = f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r>{revision}</w:p></w:body></w:document>"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


@pytest.fixture
def sample_tdoc_metadata() -> TDocMetadata:
    """Create sample TDoc metadata for testing."""
    return TDocMetadata(
        tdoc_id="S4-251234",
        url="https://www.3gpp.org/ftp/tsg_sa/SA4/s4-251234.zip",
        title="Test TDoc",
        meeting_id=113,
        source="Test Source",
        contact="test@example.com",
        tdoc_type="Test Type",
        for_purpose="Test Purpose",
        agenda_item_nbr="1.0",
        agenda_item_text="Test Agenda Item",
        status="available",
        meeting_name="Test Meeting",
        is_revision_of=None,
        file_size=None,
        date_created=None,
        validated=False,
        validation_failed=False,
    )


@pytest.fixture
def checkout_dir(tmp_path: Path) -> Path:
    """Create temporary checkout directory."""
    return tmp_path / "checkout"


def _make_metadata(tdoc_id: str, url: str | None, *, status: str | None = None) -> TDocMetadata:
    return TDocMetadata(
        tdoc_id=tdoc_id,
        meeting_id=1,
        title=tdoc_id,
        source="x",
        contact="x",
        agenda_item_nbr="1.0",
        url=url,
        tdoc_type="x",
        for_purpose="x",
        agenda_item_text="x",
        status=status,
        meeting_name="x",
        is_revision_of=None,
        file_size=None,
        date_created=None,
        validated=False,
        validation_failed=False,
    )
