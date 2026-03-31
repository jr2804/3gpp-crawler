from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tdoc_crawler.specs.downloads import SpecDownloads


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def downloader(mock_db: MagicMock, tmp_path: Path) -> SpecDownloads:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    http_cache_file = cache_dir / "http-cache.sqlite3"
    return SpecDownloads(mock_db, http_cache_file=http_cache_file)


class TestSpecDownloads:
    # This test verifies that checkout_specs resolves URL and uses doc-only logic.
    @patch("tdoc_crawler.specs.downloads.HTTPZipReader")
    def test_checkout_specs_doc_only_remote(self, MockHTTPZipReader: MagicMock, downloader: SpecDownloads, mock_db: MagicMock, tmp_path: Path) -> None:
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

        async def mock_extract(info: Any, output: Any) -> AsyncGenerator[int]:
            extracted_entries.append(info)
            # Simulate extracting by writing placeholder bytes
            output.write(b"test content")
            yield 12  # bytes written

        mock_reader.extract = mock_extract

        # Set up async context manager on the return value
        async def mock_aenter(self: Any) -> Any:
            return mock_reader

        async def mock_aexit(self: Any, *args: Any) -> None:
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
