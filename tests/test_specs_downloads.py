from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tdoc_crawler.config import CacheManager
from tdoc_crawler.specs.downloads import SpecDownloads


@pytest.fixture  # noqa: ANN201
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture  # noqa: ANN201
def mock_cache_manager(tmp_path: Path) -> CacheManager:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return CacheManager(root_path=cache_dir, name="test")


@pytest.fixture  # noqa: ANN201
def downloader(mock_db: MagicMock, mock_cache_manager: CacheManager) -> SpecDownloads:
    mock_cache_manager.register()
    return SpecDownloads(mock_db, cache_manager_name="test")


class TestSpecDownloads:
    # This test verifies that checkout_specs resolves URL and uses doc-only logic.
    @patch("tdoc_crawler.specs.downloads.HTTPZipReader")
    def test_checkout_specs_doc_only_remote(self, MockHTTPZipReader: MagicMock, downloader: SpecDownloads, mock_db: MagicMock, tmp_path: Path) -> None:  # noqa: ANN001
        """Test that checkout_specs resolves URL and uses zipinspect for doc-only."""
        specs = ["26.132"]
        checkout_dir = tmp_path / "checkout"

        # Setup Mock Reader
        mock_reader = MagicMock()

        entry = MagicMock()
        entry.path = "26132.doc"  # Use .path (not .filename)
        mock_reader.entries = [entry]

        # extract() is an async generator - track it with a wrapper mock
        extracted_entries: list[MagicMock] = []

        async def mock_extract(info, output):
            extracted_entries.append(info)
            # Simulate extracting by writing placeholder bytes
            output.write(b"test content")
            yield 12  # bytes written

        mock_reader.extract = mock_extract

        # Set up async context manager on the return value
        async def mock_aenter(self):
            return mock_reader

        async def mock_aexit(self, *args):
            return None

        MockHTTPZipReader.return_value.__aenter__ = mock_aenter
        MockHTTPZipReader.return_value.__aexit__ = mock_aexit

        # We rely on _resolve_spec_url
        with patch.object(downloader, "_resolve_spec_url", return_value=("http://example.com/26132-j00.zip", "26132-j00.zip"), create=True) as mock_resolve:
            # Execute
            downloader.checkout_specs(specs, doc_only=True, checkout_dir=checkout_dir)

            # Assert
            mock_resolve.assert_called_with("26.132", "latest")

            # Verify HTTPZipReader called
            MockHTTPZipReader.assert_called_with("http://example.com/26132-j00.zip")

            # Verify extract called with correct entry
            assert len(extracted_entries) == 1
            assert extracted_entries[0].path == "26132.doc"
