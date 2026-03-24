"""HTTP client factory with hishel caching support.

Re-exports from session module for backward-compatible imports:
    from tdoc_crawler.http_client import create_cached_session
    from tdoc_crawler.http_client import download_to_file
    from tdoc_crawler.http_client import PoolConfig
"""

from __future__ import annotations

from tdoc_crawler.http_client.session import PoolConfig, create_cached_session, download_to_file

__all__ = ["PoolConfig", "create_cached_session", "download_to_file"]
