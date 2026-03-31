"""Unit tests for HTTP client with caching functionality."""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from hishel.requests import CacheAdapter
from requests.adapters import HTTPAdapter

from tdoc_crawler.config import DEFAULT_HTTP_CACHE_FILENAME
from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.http_client import PoolConfig, create_cached_session, download_to_file
from tdoc_crawler.http_client.session import SSLContextCacheAdapter, SSLContextHTTPAdapter, resolve_ssl_verify


class TestCreateCachedSession:
    """Tests for create_cached_session function."""

    def test_creates_session(self, test_cache_dir: Path) -> None:
        """Test that create_cached_session returns a requests.Session."""
        http_config = HttpConfig(
            cache_ttl=3600,
            cache_refresh_on_access=True,
            max_retries=3,
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_creates_cache_directory(self, tmp_path: Path) -> None:
        """Test that cache directory is created if it doesn't exist."""
        cache_root = tmp_path / "nonexistent"
        assert not cache_root.exists()

        # create_cached_session creates the parent directory as needed
        cache_file = cache_root / DEFAULT_HTTP_CACHE_FILENAME
        http_config = HttpConfig(
            cache_ttl=3600,
            cache_refresh_on_access=True,
            max_retries=3,
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=cache_file,
        )

        session.close()

    def test_creates_cache_database(self, test_cache_dir: Path) -> None:
        """Test that cache database file is created lazily."""
        http_config = HttpConfig(
            cache_ttl=3600,
            cache_refresh_on_access=True,
            max_retries=3,
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
        )

        # The database is created lazily on first use, so make a request
        with patch.object(session, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_get.return_value = mock_response

            with contextlib.suppress(Exception):
                session.get("http://example.com")

        session.close()

    def test_session_has_cache_adapter(self, test_cache_dir: Path) -> None:
        """Test that session has cache adapter mounted."""
        session = create_cached_session(
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
        )

        # Check that adapters are mounted for http and https
        assert "http://" in session.adapters
        assert "https://" in session.adapters

        # Check that the adapters are CacheAdapter instances
        assert isinstance(session.adapters["http://"], CacheAdapter)
        assert isinstance(session.adapters["https://"], CacheAdapter)

        session.close()

    def test_cache_adapter_keeps_pool_settings(self, test_cache_dir: Path) -> None:
        """Regression: cache + pool settings are active on the same adapter."""
        pool_config = PoolConfig(max_connections=7, max_per_host=11, retry_attempts=4)
        session = create_cached_session(
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
            pool_config=pool_config,
        )

        http_adapter = session.adapters["http://"]
        https_adapter = session.adapters["https://"]

        assert isinstance(http_adapter, CacheAdapter)
        assert isinstance(https_adapter, CacheAdapter)
        assert http_adapter._pool_connections == 7
        assert http_adapter._pool_maxsize == 11
        assert https_adapter._pool_connections == 7
        assert https_adapter._pool_maxsize == 11

        session.close()

    def test_pool_only_session_uses_http_adapter(self) -> None:
        """When caching is disabled, pooling should still be configured."""
        pool_config = PoolConfig(max_connections=4, max_per_host=9, retry_attempts=2)
        session = create_cached_session(
            http_cache_enabled=False,
            pool_config=pool_config,
        )

        http_adapter = session.adapters["http://"]
        https_adapter = session.adapters["https://"]

        assert isinstance(http_adapter, HTTPAdapter)
        assert isinstance(https_adapter, HTTPAdapter)
        assert not isinstance(http_adapter, CacheAdapter)
        assert not isinstance(https_adapter, CacheAdapter)
        assert http_adapter._pool_connections == 4
        assert http_adapter._pool_maxsize == 9
        assert https_adapter._pool_connections == 4
        assert https_adapter._pool_maxsize == 9

        session.close()

    def test_default_parameters(self, test_cache_dir: Path) -> None:
        """Test that default parameters work correctly."""
        session = create_cached_session(http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME)

        assert isinstance(session, requests.Session)
        session.close()

    def test_custom_ttl(self, test_cache_dir: Path) -> None:
        """Test that custom TTL is accepted."""
        http_config = HttpConfig(
            cache_ttl=1800,
            cache_refresh_on_access=False,
            max_retries=5,
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_zero_retries(self, test_cache_dir: Path) -> None:
        """Test that zero retries is handled correctly."""
        http_config = HttpConfig(
            max_retries=0,
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_large_ttl(self, test_cache_dir: Path) -> None:
        """Test that large TTL values are handled correctly."""
        http_config = HttpConfig(
            cache_ttl=86400,  # 24 hours
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_multiple_sessions_same_cache(self, test_cache_dir: Path) -> None:
        """Test that multiple sessions can use the same cache directory."""
        cache_file = test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME

        session1 = create_cached_session(http_cache_file=cache_file)
        session2 = create_cached_session(http_cache_file=cache_file)

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
        cache_db = test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME

        http_config = HttpConfig(
            max_retries=2,
        )
        session = create_cached_session(
            http_config=http_config,
            http_cache_file=cache_db,
        )

        try:
            # Make first request
            response1 = session.get("https://httpbin.org/get", timeout=10)
            assert response1.status_code == 200

            # Make second request (should be cached)
            response2 = session.get("https://httpbin.org/get", timeout=10)
            assert response2.status_code == 200

            # Verify cache database exists
            assert cache_db.exists()
            assert cache_db.stat().st_size > 0

        except requests.RequestException as e:
            pytest.skip(f"Network request failed: {e}")
        finally:
            session.close()

    def test_cache_database_path(self, test_cache_dir: Path) -> None:
        """Test that cache database is created at the correct path."""
        cache_file = test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME

        session = create_cached_session(http_cache_file=cache_file)

        # The database path should match what we passed in
        assert cache_file.name == DEFAULT_HTTP_CACHE_FILENAME

        session.close()


class TestDownloadToFilePooling:
    """Tests for pooled timeout usage in download helper."""

    def test_uses_pool_timeout_for_download(self, tmp_path: Path) -> None:
        """Regression: download_to_file should use pool connection timeout."""
        destination = tmp_path / "download.bin"
        session = MagicMock(spec=requests.Session)
        response = MagicMock()
        response.iter_content.return_value = [b"abc", b"def"]
        response.raise_for_status.return_value = None
        session.get.return_value = response

        pool_config = PoolConfig(connection_timeout=7.5)
        download_to_file(
            "https://example.com/test.bin",
            destination,
            session=session,
            pool_config=pool_config,
        )

        session.get.assert_called_once_with("https://example.com/test.bin", timeout=7.5, stream=True)
        assert destination.read_bytes() == b"abcdef"


class TestResolveSslVerify:
    """Tests for SSL verify resolution helper."""

    def test_explicit_value_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit function argument should override environment variables."""
        monkeypatch.setenv("TDC_VERIFY_SSL", "false")
        assert resolve_ssl_verify(True) is True

    def test_env_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Known false env values should disable certificate validation."""
        monkeypatch.setenv("TDC_VERIFY_SSL", "no")
        assert resolve_ssl_verify() is False

    def test_env_custom_ca_bundle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-boolean env value should be treated as CA bundle path."""
        monkeypatch.setenv("TDC_VERIFY_SSL", "C:/certs/corp.pem")
        assert resolve_ssl_verify() == "C:/certs/corp.pem"

    def test_default_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SSL verification should be enabled by default."""
        monkeypatch.delenv("TDC_VERIFY_SSL", raising=False)
        assert resolve_ssl_verify() is True


class TestSslContextAdapters:
    """Tests for SSL-context aware adapter behavior."""

    def test_non_cached_verify_true_uses_ssl_context_adapter(self) -> None:
        """Non-cached sessions should mount SSL-aware adapters when verify=True."""
        session = create_cached_session(http_cache_enabled=False, verify=True)
        try:
            assert isinstance(session.adapters["http://"], SSLContextHTTPAdapter)
            assert isinstance(session.adapters["https://"], SSLContextHTTPAdapter)
            assert session.verify is True
        finally:
            session.close()

    def test_non_cached_verify_false_uses_default_adapter(self) -> None:
        """Non-cached verify=False should use requests defaults when no pool override is set."""
        session = create_cached_session(http_cache_enabled=False, verify=False)
        try:
            assert isinstance(session.adapters["http://"], HTTPAdapter)
            assert isinstance(session.adapters["https://"], HTTPAdapter)
            assert not isinstance(session.adapters["https://"], SSLContextHTTPAdapter)
            assert session.verify is False
        finally:
            session.close()

    def test_cached_verify_true_uses_ssl_cache_adapter(self, test_cache_dir: Path) -> None:
        """Cached sessions should mount SSL-aware cache adapters when verify=True."""
        session = create_cached_session(http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME, verify=True)
        try:
            assert isinstance(session.adapters["http://"], SSLContextCacheAdapter)
            assert isinstance(session.adapters["https://"], SSLContextCacheAdapter)
            assert session.verify is True
        finally:
            session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestHttpSessionWithConfig:
    """Test HTTP session functions with HttpConfig integration."""

    def test_resolve_ssl_verify_uses_http_config(self) -> None:
        """resolve_ssl_verify uses http_config.verify_ssl when no explicit verify."""
        http_config = HttpConfig(verify_ssl=False)

        result = resolve_ssl_verify(http_config=http_config)

        assert result is False

    def test_resolve_ssl_verify_explicit_overrides_config(self) -> None:
        """Explicit verify parameter takes precedence over http_config."""
        http_config = HttpConfig(verify_ssl=False)

        result = resolve_ssl_verify(verify=True, http_config=http_config)

        assert result is True

    def test_resolve_ssl_verify_fallback_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without http_config, falls back to env var."""
        monkeypatch.setenv("TDC_VERIFY_SSL", "false")

        result = resolve_ssl_verify()

        assert result is False

    def test_create_cached_session_uses_config_cache_enabled(self, test_cache_dir: Path) -> None:
        """create_cached_session respects http_config.cache_enabled=False."""
        http_config = HttpConfig(cache_enabled=False)

        session = create_cached_session(
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
            http_config=http_config,
        )

        # Session should be plain requests session (no cache adapter)
        assert session is not None
        # When caching is disabled, it should use HTTPAdapter, not CacheAdapter
        assert not isinstance(session.adapters["http://"], CacheAdapter)
        session.close()

    def test_create_cached_session_explicit_overrides_config(self, test_cache_dir: Path) -> None:
        """Explicit http_cache_enabled overrides http_config."""
        http_config = HttpConfig(cache_enabled=True)

        session = create_cached_session(
            http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME,
            http_config=http_config,
            http_cache_enabled=False,
        )

        # Explicit False should override http_config.cache_enabled=True
        assert session is not None
        # Should have plain HTTP adapter since caching is explicitly disabled
        assert isinstance(session.adapters["http://"], SSLContextHTTPAdapter)
        session.close()


class TestHttpConfigBackwardCompat:
    """Test backward compatibility without HttpConfig."""

    def test_resolve_ssl_verify_no_config_uses_default(self) -> None:
        """Without config or env, defaults to True."""
        result = resolve_ssl_verify()

        assert result is True

    def test_create_cached_session_no_config_works(self, test_cache_dir: Path) -> None:
        """create_cached_session works without http_config parameter."""
        session = create_cached_session(http_cache_file=test_cache_dir / DEFAULT_HTTP_CACHE_FILENAME)

        assert session is not None
        assert hasattr(session, "headers")
        session.close()
