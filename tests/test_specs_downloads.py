from unittest.mock import MagicMock, patch

import pytest

from tdoc_crawler.specs.downloads import SpecDownloads


@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def downloader(mock_db):
    return SpecDownloads(mock_db)

class TestSpecDownloads:
    # This test verifies that checkout_specs resolves URL and uses doc-only logic.
    @patch("tdoc_crawler.specs.downloads.HTTPZipReader")
    def test_checkout_specs_doc_only_remote(self, MockHTTPZipReader, downloader, mock_db, tmp_path) -> None:
        """Test that checkout_specs resolves URL and uses zipinspect for doc-only."""
        from unittest.mock import AsyncMock  # Import inside to avoid top-level import issue if not needed

        specs = ["26.132"]
        checkout_dir = tmp_path / "checkout"

        # Setup Mock Reader
        mock_reader = MagicMock()
        mock_reader.load_entries = AsyncMock()
        mock_reader.extract = AsyncMock()

        entry = MagicMock()
        entry.filename = "26132.doc"
        mock_reader.entries = [entry]

        # Mocking async context manager manually
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_reader)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        MockHTTPZipReader.return_value = mock_cm

        # We rely on _resolve_spec_url
        with patch.object(downloader, '_resolve_spec_url', return_value=("http://example.com/26132-j00.zip", "26132-j00.zip"), create=True) as mock_resolve:
            # Execute
            downloader.checkout_specs(specs, doc_only=True, checkout_dir=checkout_dir)

            # Assert
            mock_resolve.assert_called_with("26.132", "latest")

            # Verify HTTPZipReader called
            MockHTTPZipReader.assert_called_with("http://example.com/26132-j00.zip")

            # Verify load_entries called
            mock_reader.load_entries.assert_called_once()

            # Verify extract called with correct entries
            assert mock_reader.extract.call_count == 1
            # Check args
            args, kwargs = mock_reader.extract.call_args
            assert args[0][0].filename == "26132.doc"
            assert kwargs['out_dir'] == checkout_dir / "Specs" / "archive" / "26_series" / "26.132"
