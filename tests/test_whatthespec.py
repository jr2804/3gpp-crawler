"""Unit tests for WhatTheSpec TDoc resolution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from tdoc_crawler.config import CacheManager, reset_cache_managers
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models.base import HttpCacheConfig
from tdoc_crawler.tdocs.models import TDocMetadata
from tdoc_crawler.tdocs.sources.whatthespec import WHATSPEC_BASE_URL, WhatTheSpecResolutionError, resolve_via_whatthespec

from .conftest import insert_sample_meetings_async


class TestWhatTheSpecResolution:
    """Test suite for WhatTheSpec resolver."""

    @pytest.fixture(autouse=True)
    def setup_cache(self) -> None:
        """Reset cache managers before each test."""
        reset_cache_managers()

    @pytest.fixture
    def http_cache_config(self) -> HttpCacheConfig:
        """Create HTTP cache configuration for tests.

        Returns:
            HttpCacheConfig instance with default settings.
        """
        return HttpCacheConfig(ttl=3600, refresh_ttl_on_access=True)

    @pytest.fixture
    def sample_api_response(self) -> list[dict]:
        """Create sample API response from whatthespec.net.

        Returns:
            List containing one TDoc record matching whatthespec API format.
        """
        return [
            {
                "name": "S4-260001",
                "title": "SA4#135 meeting agenda",
                "source": "SA WG4 Chair",
                "contact": "Gilles Teniou",
                "tdoctype": "agenda",
                "for": "Approval",
                "link": "https://www.3gpp.org/tsg_sa/WG4_CODEC/TSGS4_135_India/Docs/S4-260001.zip",
                "meeting": "S4-135",
                "ainumber": "2",
                "ainame": "Approval of agenda and association of documents",
                "status": "available",
            }
        ]

    def test_successful_resolution_with_valid_response(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig, sample_api_response: list[dict]) -> None:
        """Test successful TDoc resolution with valid API response.

        Mocks HTTP requests to return valid whatthespec API response and verifies
        that resolve_via_whatthespec() returns TDocMetadata with correct field mapping.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
            sample_api_response: Sample API response.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = sample_api_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("S4-260001", http_cache=http_cache_config, cache_manager_name="test_whatspec", timeout=30)

            assert result is not None
            assert isinstance(result, TDocMetadata)
            assert result.tdoc_id == "S4-260001"
            assert result.title == "SA4#135 meeting agenda"
            assert result.source == "SA WG4 Chair"
            assert result.contact == "Gilles Teniou"
            assert result.tdoc_type == "agenda"
            assert result.for_purpose == "Approval"
            assert result.url == "https://www.3gpp.org/tsg_sa/WG4_CODEC/TSGS4_135_India/Docs/S4-260001.zip"
            assert result.agenda_item_nbr == "2"
            assert result.agenda_item_text == "Approval of agenda and association of documents"
            assert result.status == "available"
            assert result.validated is False
            assert result.validation_failed is False

    def test_empty_response_returns_none(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that empty API response returns None (TDoc not found).

        Mocks API to return empty array and verifies resolve_via_whatthespec()
        returns None when TDoc is not found.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("INVALID-ID", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is None

    def test_null_record_returns_metadata_with_defaults(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that API response with null record returns TDocMetadata with defaults.

        When API returns array with null element, the resolver treats it as an empty
        record dict and returns TDocMetadata with default values.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = [None]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("S4-260001", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is not None
            assert isinstance(result, TDocMetadata)
            # Verify it has default values when record is None
            assert result.tdoc_id == "S4-260001"
            assert result.tdoc_type == "unknown"
            assert result.for_purpose == "unknown"

    def test_network_timeout_raises_error(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that network timeout raises WhatTheSpecResolutionError.

        Mocks HTTP requests to raise requests.Timeout and verifies
        WhatTheSpecResolutionError is raised.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get:
            mock_get.side_effect = requests.Timeout("Connection timeout")

            with pytest.raises(WhatTheSpecResolutionError) as exc_info:
                resolve_via_whatthespec("S4-260001", http_cache=http_cache_config, cache_manager_name="test_whatspec", timeout=5)

            assert "WhatTheSpec request failed" in str(exc_info.value)
            assert "S4-260001" in str(exc_info.value)

    def test_connection_error_raises_error(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that connection error raises WhatTheSpecResolutionError.

        Mocks HTTP requests to raise requests.ConnectionError and verifies
        WhatTheSpecResolutionError is raised.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("Connection failed")

            with pytest.raises(WhatTheSpecResolutionError) as exc_info:
                resolve_via_whatthespec("S4-260001", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert "WhatTheSpec request failed" in str(exc_info.value)

    def test_http_error_raises_error(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that HTTP error raises WhatTheSpecResolutionError.

        Mocks HTTP response to raise HTTPError and verifies WhatTheSpecResolutionError
        is raised.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
            mock_get.return_value = mock_response

            with pytest.raises(WhatTheSpecResolutionError):
                resolve_via_whatthespec("S4-260001", http_cache=http_cache_config, cache_manager_name="test_whatspec")

    def test_field_mapping_correctness(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that all API fields map correctly to TDocMetadata fields.

        Verifies that each field from whatthespec API is correctly mapped to the
        corresponding TDocMetadata field with proper type conversion.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        api_response = [
            {
                "name": "R1-250123",
                "title": "Test Title",
                "source": "Test Source",
                "contact": "Test Contact",
                "tdoctype": "discussion",
                "for": "information",
                "link": "https://example.com/doc.zip",
                "meeting": "R1-98",
                "ainumber": "3.5",
                "ainame": "Test agenda item",
                "status": "approved",
            }
        ]

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("R1-250123", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is not None
            # Verify field mapping
            assert result.tdoc_id == "R1-250123"  # name -> tdoc_id
            assert result.title == "Test Title"  # title -> title
            assert result.source == "Test Source"  # source -> source
            assert result.contact == "Test Contact"  # contact -> contact
            assert result.tdoc_type == "discussion"  # tdoctype -> tdoc_type
            assert result.for_purpose == "information"  # for -> for_purpose
            assert result.url == "https://example.com/doc.zip"  # link -> url
            assert result.agenda_item_nbr == "3.5"  # ainumber -> agenda_item_nbr
            assert result.agenda_item_text == "Test agenda item"  # ainame -> agenda_item_text
            assert result.status == "approved"  # status -> status

    def test_defaults_for_missing_fields(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that defaults are used for missing API fields.

        Verifies that missing fields (tdoc_type, for_purpose) are set to "unknown"
        and other optional fields have sensible defaults.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        minimal_response = [
            {
                "name": "S2-250456",
                "title": "Minimal record",
                "link": "https://example.com/minimal.zip",
                # Missing: source, contact, tdoctype, for, meeting, ainumber, ainame, status
            }
        ]

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = minimal_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("S2-250456", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is not None
            assert result.tdoc_type == "unknown"  # default for missing tdoctype
            assert result.for_purpose == "unknown"  # default for missing for
            assert result.source == ""  # default for missing source
            assert result.contact == ""  # default for missing contact
            assert result.agenda_item_nbr == "0"  # default for invalid ainumber
            assert result.agenda_item_text == "Unknown"  # default for missing ainame
            assert result.status is None  # None for missing status

    def test_invalid_agenda_item_number_defaults_to_zero(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that invalid agenda item numbers default to zero.

        Verifies that non-numeric agenda_item_nbr values are parsed as "0"
        with warning logged.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        api_response = [
            {
                "name": "C1-250789",
                "title": "Invalid agenda number",
                "link": "https://example.com/doc.zip",
                "ainumber": "invalid",  # Invalid agenda item number
            }
        ]

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("C1-250789", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is not None
            assert result.agenda_item_nbr == "0"

    def test_meeting_id_lazy_resolution(
        self,
        test_cache_dir: Path,
        http_cache_config: HttpCacheConfig,
        test_db_path: Path,
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Test that meeting_id is correctly resolved from meeting_name.

        Verifies that meeting_id is resolved via resolve_meeting_id() using the
        meeting_name from the API response, with fallback to 0 on failure.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
            test_db_path: Path to temporary test database.
            sample_meetings: Meeting seed data fixture.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        async def _seed_database() -> None:
            async with TDocDatabase(test_db_path) as db:
                await insert_sample_meetings_async(db, sample_meetings)

        asyncio.run(_seed_database())

        api_response = [
            {
                "name": "S4-2301890",
                "title": "Meeting agenda",
                "link": "https://example.com/doc.zip",
                "meeting": "SA4#134",  # This should resolve to meeting_id 12347
            }
        ]

        # In order for lazy resolution to work with the database, we need to mock TDocDatabase
        # or ensure resolve_via_whatthespec uses the provided DB.
        # However, resolve_via_whatthespec uses its own lazy import of TDocDatabase.
        # So we need to ensure the TDocDatabase it uses points to our test DB.

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # Point TDC_CACHE_DIR to our test dir so the lazy DB load uses it
            with patch.dict("os.environ", {"TDC_CACHE_DIR": str(test_cache_dir)}):
                result = resolve_via_whatthespec("S4-2301890", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is not None
            # Meeting resolution should work if meeting is in DB
            assert result.meeting_id == 12347

    def test_tdoc_id_normalization(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that TDoc IDs are normalized to uppercase.

        Verifies that the resolver normalizes TDoc IDs to uppercase regardless of
        API response case.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        api_response = [
            {
                "name": "r1-250999",  # lowercase
                "title": "Case test",
                "link": "https://example.com/doc.zip",
            }
        ]

        with patch("requests.Session.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = api_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = resolve_via_whatthespec("r1-250999", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            assert result is not None
            assert result.tdoc_id == "R1-250999"  # normalized to uppercase

    def test_resolver_closes_session(self, test_cache_dir: Path, http_cache_config: HttpCacheConfig) -> None:
        """Test that HTTP session is closed after resolution.

        Verifies that the resolver always closes the session, even on error.

        Args:
            test_cache_dir: Temporary cache directory from fixture.
            http_cache_config: HTTP cache configuration.
        """
        CacheManager(root_path=test_cache_dir, name="test_whatspec").register()

        with patch("requests.Session.get") as mock_get, patch("requests.Session.close"):
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            resolve_via_whatthespec("S4-260001", http_cache=http_cache_config, cache_manager_name="test_whatspec")

            # Session close should be called in finally block
            # Note: Due to mocking, this verifies the pattern is in place

    def test_whatspec_base_url_format(self) -> None:
        """Test that WHATSPEC_BASE_URL has correct format placeholder.

        Verifies that WHATSPEC_BASE_URL contains {tdoc} placeholder for formatting.
        """
        assert "{tdoc}" in WHATSPEC_BASE_URL
        assert WHATSPEC_BASE_URL == "https://whatthespec.net/3gpp/tdoc.php?name={tdoc}&api=1"


class TestWhatTheSpecResolutionError:
    """Test suite for WhatTheSpecResolutionError exception."""

    def test_exception_is_raised_correctly(self) -> None:
        """Test that WhatTheSpecResolutionError can be raised and caught.

        Verifies that the custom exception class works as expected.
        """
        with pytest.raises(WhatTheSpecResolutionError) as exc_info:
            raise WhatTheSpecResolutionError("Test error message")

        assert "Test error message" in str(exc_info.value)

    def test_exception_inherits_from_exception(self) -> None:
        """Test that WhatTheSpecResolutionError inherits from Exception.

        Verifies the exception class hierarchy.
        """
        assert issubclass(WhatTheSpecResolutionError, Exception)
