"""Tests for TDoc checkout functionality."""

import io
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from packaging.version import Version

from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.operations.checkout import checkout_tdoc, get_checked_out_tdocs, get_checkout_path


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
        agenda_item_nbr=Version("1.0"),
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
            agenda_item_nbr=Version("1.0"),
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
            agenda_item_nbr=Version("1.0"),
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
            agenda_item_nbr=Version("1.0"),
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
