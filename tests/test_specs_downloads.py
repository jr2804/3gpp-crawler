from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tdoc_crawler.specs.downloads import SpecDownloads


class TestSpecDownloads:
    # This test verifies that checkout_specs resolves URL and uses doc-only logic.
    @patch("tdoc_crawler.specs.downloads.RemoteZipFile")
    def test_checkout_specs_doc_only_remote(self, MockRemoteZipFile: MagicMock, downloader: SpecDownloads, mock_db: MagicMock, tmp_path: Path) -> None:
        """Test that checkout_specs resolves URL and uses unzip-http for doc-only."""
        specs = ["26.132"]
        checkout_dir = tmp_path / "checkout"

        # Setup Mock RemoteZipFile
        mock_rzf = MagicMock()
        mock_rzf.namelist.return_value = ["26132.doc"]

        # Mock open() to return a file-like object with test content
        mock_file = MagicMock()
        mock_file.read.return_value = b"test content"
        mock_rzf.open.return_value = mock_file

        MockRemoteZipFile.return_value = mock_rzf

        # We rely on _resolve_spec_url
        with patch.object(downloader, "_resolve_spec_url", return_value=("http://example.com/26132-j00.zip", "26132-j00.zip"), create=True) as mock_resolve:
            # Execute
            downloader.checkout_specs(specs, doc_only=True, checkout_dir=checkout_dir)

            # Assert
            mock_resolve.assert_called_with("26.132", "latest")

            # Verify RemoteZipFile called
            MockRemoteZipFile.assert_called_with("http://example.com/26132-j00.zip")

            # Verify open called with correct filename
            mock_rzf.open.assert_called_with("26132.doc")


@pytest.fixture
def downloader(mock_db: MagicMock, tmp_path: Path) -> SpecDownloads:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    http_cache_file = cache_dir / "http-cache.sqlite3"
    return SpecDownloads(mock_db, http_cache_file=http_cache_file)


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()
