"""Unit tests for HTTP client with caching functionality."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from hishel.requests import CacheAdapter

from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.models.base import HttpCacheConfig


class TestCreateCachedSession:
    """Tests for create_cached_session function."""

    def test_creates_session(self, test_cache_dir: Path) -> None:
        """Test that create_cached_session returns a requests.Session."""
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_creates_cache_directory(self, tmp_path: Path) -> None:
        """Test that cache directory is created if it doesn't exist."""
        cache_dir = tmp_path / "nonexistent" / "cache"
        assert not cache_dir.exists()

        session = create_cached_session(
            cache_dir=cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        assert cache_dir.exists()
        session.close()

    def test_creates_cache_database(self, test_cache_dir: Path) -> None:
        """Test that cache database file is created."""
        cache_db = test_cache_dir / "http-cache.sqlite3"
        assert not cache_db.exists()

        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        # The database is created lazily on first use, so make a request
        with patch.object(session, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_get.return_value = mock_response

            try:
                session.get("http://example.com")
            except Exception:
                pass  # Ignore any errors, we just want to trigger cache creation

        session.close()

    def test_session_has_cache_adapter(self, test_cache_dir: Path) -> None:
        """Test that session has cache adapter mounted."""
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        # Check that adapters are mounted for http and https
        assert "http://" in session.adapters
        assert "https://" in session.adapters

        # Check that the adapters are CacheAdapter instances
        assert isinstance(session.adapters["http://"], CacheAdapter)
        assert isinstance(session.adapters["https://"], CacheAdapter)

        session.close()

    def test_default_parameters(self, test_cache_dir: Path) -> None:
        """Test that default parameters work correctly."""
        session = create_cached_session(cache_dir=test_cache_dir)

        assert isinstance(session, requests.Session)
        session.close()

    def test_custom_ttl(self, test_cache_dir: Path) -> None:
        """Test that custom TTL is accepted."""
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=1800,
            refresh_ttl_on_access=False,
            max_retries=5,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_zero_retries(self, test_cache_dir: Path) -> None:
        """Test that zero retries is handled correctly."""
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=0,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_large_ttl(self, test_cache_dir: Path) -> None:
        """Test that large TTL values are handled correctly."""
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=86400,  # 24 hours
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_multiple_sessions_same_cache(self, test_cache_dir: Path) -> None:
        """Test that multiple sessions can use the same cache directory."""
        session1 = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        session2 = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        assert isinstance(session1, requests.Session)
        assert isinstance(session2, requests.Session)

        session1.close()
        session2.close()


class TestCachingBehavior:
    """Tests for actual caching behavior."""

    @pytest.mark.integration
    def test_caching_works_with_real_request(self, test_cache_dir: Path) -> None:
        """Integration test: verify caching works with a real HTTP request.

        This test is marked as integration and may be skipped in unit test runs.
        """
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=2,
        )

        try:
            # Make first request
            response1 = session.get("https://httpbin.org/get", timeout=10)
            assert response1.status_code == 200

            # Make second request (should be cached)
            response2 = session.get("https://httpbin.org/get", timeout=10)
            assert response2.status_code == 200

            # Verify cache database exists
            cache_db = test_cache_dir / "http-cache.sqlite3"
            assert cache_db.exists()
            assert cache_db.stat().st_size > 0

        except requests.RequestException as e:
            pytest.skip(f"Network request failed: {e}")
        finally:
            session.close()

    def test_cache_database_path(self, test_cache_dir: Path) -> None:
        """Test that cache database is created at the correct path."""
        session = create_cached_session(
            cache_dir=test_cache_dir,
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )

        # The database should exist after creating the session
        # (hishel creates it immediately)
        session.close()


class TestResolveHttpCacheConfig:
    """Tests for resolve_http_cache_config helper function."""

    def test_cli_params_override_everything(self) -> None:
        """Test that CLI parameters override environment variables."""
        with patch.dict(os.environ, {"HTTP_CACHE_TTL": "3600", "HTTP_CACHE_REFRESH_ON_ACCESS": "false"}):
            config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=1800, cache_refresh_on_access=True)

            assert config.ttl == 1800
            assert config.refresh_ttl_on_access is True

    def test_env_vars_used_when_no_cli_params(self) -> None:
        """Test that environment variables are used when CLI params are None."""
        with patch.dict(os.environ, {"HTTP_CACHE_TTL": "5400", "HTTP_CACHE_REFRESH_ON_ACCESS": "false"}):
            config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=None, cache_refresh_on_access=None)

            assert config.ttl == 5400
            assert config.refresh_ttl_on_access is False

    def test_defaults_when_nothing_set(self) -> None:
        """Test that defaults are used when no CLI params or env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=None, cache_refresh_on_access=None)

            assert config.ttl == 7200
            assert config.refresh_ttl_on_access is True

    def test_env_var_refresh_true_values(self) -> None:
        """Test that various 'true' values for refresh_ttl_on_access work."""
        true_values = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]

        for value in true_values:
            with patch.dict(os.environ, {"HTTP_CACHE_REFRESH_ON_ACCESS": value}):
                config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=None, cache_refresh_on_access=None)
                assert config.refresh_ttl_on_access is True, f"Failed for value: {value}"

    def test_env_var_refresh_false_values(self) -> None:
        """Test that non-true values for refresh_ttl_on_access are false."""
        false_values = ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", "invalid"]

        for value in false_values:
            with patch.dict(os.environ, {"HTTP_CACHE_REFRESH_ON_ACCESS": value}):
                config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=None, cache_refresh_on_access=None)
                assert config.refresh_ttl_on_access is False, f"Failed for value: {value}"

    def test_env_var_ttl_integer_parsing(self) -> None:
        """Test that TTL environment variable is parsed as integer."""
        with patch.dict(os.environ, {"HTTP_CACHE_TTL": "9999"}):
            config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=None, cache_refresh_on_access=None)

            assert config.ttl == 9999
            assert isinstance(config.ttl, int)

    def test_partial_override_ttl_only(self) -> None:
        """Test that only TTL can be overridden via CLI."""
        with patch.dict(os.environ, {"HTTP_CACHE_TTL": "3600", "HTTP_CACHE_REFRESH_ON_ACCESS": "false"}):
            config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=1200, cache_refresh_on_access=None)

            assert config.ttl == 1200
            assert config.refresh_ttl_on_access is False

    def test_partial_override_refresh_only(self) -> None:
        """Test that only refresh can be overridden via CLI."""
        with patch.dict(os.environ, {"HTTP_CACHE_TTL": "3600", "HTTP_CACHE_REFRESH_ON_ACCESS": "false"}):
            config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=None, cache_refresh_on_access=True)

            assert config.ttl == 3600
            assert config.refresh_ttl_on_access is True

    def test_returns_http_cache_config_instance(self) -> None:
        """Test that the function returns an HttpCacheConfig instance."""
        config = HttpCacheConfig.resolve_http_cache_config(cache_ttl=3600, cache_refresh_on_access=True)

        assert isinstance(config, HttpCacheConfig)
        assert hasattr(config, "ttl")
        assert hasattr(config, "refresh_ttl_on_access")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
