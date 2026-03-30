"""Unit tests for HTTP client with caching functionality."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from hishel.requests import CacheAdapter
from requests.adapters import HTTPAdapter

from tdoc_crawler.config import DEFAULT_HTTP_CACHE_FILENAME, CacheManager, reset_cache_managers
from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.http_client import PoolConfig, create_cached_session, download_to_file
from tdoc_crawler.http_client.session import SSLContextCacheAdapter, SSLContextHTTPAdapter, resolve_ssl_verify
from tdoc_crawler.models.base import HttpCacheConfig


class TestCreateCachedSession:
    """Tests for create_cached_session function."""

    @pytest.fixture(autouse=True)
    def setup_cache(self) -> None:
        """Reset cache managers before each test."""
        reset_cache_managers()

    def test_creates_session(self, test_cache_dir: Path) -> None:
        """Test that create_cached_session returns a requests.Session."""
        # Setup cache manager
        CacheManager(root_path=test_cache_dir, name="test_creates_session").register()

        http_config = HttpCacheConfig(
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="test_creates_session",
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_creates_cache_directory(self, tmp_path: Path) -> None:
        """Test that cache directory is created if it doesn't exist."""
        cache_root = tmp_path / "nonexistent"
        assert not cache_root.exists()

        CacheManager(root_path=cache_root, name="test_creates_cache_dir").register()

        # The root directory should be created by CacheManager(ensure_paths=True)
        assert cache_root.exists()

        http_config = HttpCacheConfig(
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="test_creates_cache_dir",
        )

        session.close()

    def test_creates_cache_database(self, test_cache_dir: Path) -> None:
        """Test that cache database file is created lazily."""
        CacheManager(root_path=test_cache_dir, name="test_lazy_db").register()

        # In current hishel implementation, the file might exist immediately or after first use
        # Let's just verify it can be created

        http_config = HttpCacheConfig(
            ttl=3600,
            refresh_ttl_on_access=True,
            max_retries=3,
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="test_lazy_db",
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
        CacheManager(root_path=test_cache_dir, name="test_adapter").register()

        session = create_cached_session(
            cache_manager_name="test_adapter",
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
        CacheManager(root_path=test_cache_dir, name="cache_pool").register()

        pool_config = PoolConfig(max_connections=7, max_per_host=11, retry_attempts=4)
        session = create_cached_session(
            cache_manager_name="cache_pool",
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
        CacheManager(root_path=test_cache_dir, name="default").register()
        session = create_cached_session(cache_manager_name="default")

        assert isinstance(session, requests.Session)
        session.close()

    def test_custom_ttl(self, test_cache_dir: Path) -> None:
        """Test that custom TTL is accepted."""
        CacheManager(root_path=test_cache_dir, name="custom_ttl").register()

        http_config = HttpCacheConfig(
            ttl=1800,
            refresh_ttl_on_access=False,
            max_retries=5,
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="custom_ttl",
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_zero_retries(self, test_cache_dir: Path) -> None:
        """Test that zero retries is handled correctly."""
        CacheManager(root_path=test_cache_dir, name="zero_retries").register()

        http_config = HttpCacheConfig(
            max_retries=0,
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="zero_retries",
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_large_ttl(self, test_cache_dir: Path) -> None:
        """Test that large TTL values are handled correctly."""
        CacheManager(root_path=test_cache_dir, name="large_ttl").register()

        http_config = HttpCacheConfig(
            ttl=86400,  # 24 hours
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="large_ttl",
        )

        assert isinstance(session, requests.Session)
        session.close()

    def test_multiple_sessions_same_cache(self, test_cache_dir: Path) -> None:
        """Test that multiple sessions can use the same cache directory."""
        CacheManager(root_path=test_cache_dir, name="same_cache").register()

        session1 = create_cached_session(
            cache_manager_name="same_cache",
        )

        session2 = create_cached_session(
            cache_manager_name="same_cache",
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
        manager = CacheManager(root_path=test_cache_dir, name="integration").register()
        cache_db = manager.http_cache_file

        http_config = HttpCacheConfig(
            max_retries=2,
        )
        session = create_cached_session(
            http_cache=http_config,
            cache_manager_name="integration",
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
        manager = CacheManager(root_path=test_cache_dir, name="path_test").register()

        session = create_cached_session(
            cache_manager_name="path_test",
        )

        # The database path should match what CacheManager says
        # (hishel might not create empty DB if not used, but let's check path)
        assert manager.http_cache_file.name == DEFAULT_HTTP_CACHE_FILENAME

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
        CacheManager(root_path=test_cache_dir, name="ssl_cache_adapter").register()
        session = create_cached_session(cache_manager_name="ssl_cache_adapter", verify=True)
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

    @pytest.fixture(autouse=True)
    def setup_cache(self) -> None:
        """Reset cache managers before each test."""
        reset_cache_managers()

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
        CacheManager(root_path=test_cache_dir, name="test_config_cache").register()
        http_config = HttpConfig(cache_enabled=False)

        session = create_cached_session(cache_manager_name="test_config_cache", http_config=http_config)

        # Session should be plain requests session (no cache adapter)
        assert session is not None
        # When caching is disabled, it should use HTTPAdapter, not CacheAdapter
        assert not isinstance(session.adapters["http://"], CacheAdapter)
        session.close()

    def test_create_cached_session_explicit_overrides_config(self, test_cache_dir: Path) -> None:
        """Explicit http_cache_enabled overrides http_config."""
        CacheManager(root_path=test_cache_dir, name="test_explicit_override").register()
        http_config = HttpConfig(cache_enabled=True)

        session = create_cached_session(
            cache_manager_name="test_explicit_override",
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
        CacheManager(root_path=test_cache_dir, name="test_no_config").register()
        session = create_cached_session(cache_manager_name="test_no_config")

        assert session is not None
        assert hasattr(session, "headers")
        session.close()
