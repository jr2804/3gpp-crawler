# HttpClientProvider Abstraction Design

**Date**: 2026-03-02  
**Feature**: Dependency Injection Refactoring Planning  
**Branch**: `001-di-refactoring-plan`  
**Status**: Draft

## Overview

The HttpClientProvider abstraction wraps HTTP session creation and management, enabling testability and flexibility in HTTP client implementation. This addresses the current pattern where `create_cached_session()` is called directly in multiple locations with redundant configuration.

## Problem Statement

Current instantiation pattern (from analysis):

```python
# Multiple locations with session creation
# CLI (src/tdoc_crawler/cli/app.py:79)
with create_cached_session() as session:
    response = session.get(url)

# WhatTheSpec (src/tdoc_crawler/tdocs/sources/whatthespec.py:52)
temp_session = create_cached_session(
    cache_manager_name=cache_manager_name,
    http_cache=http_cache
)

# Download helper (src/tdoc_crawler/http_client.py:55)
temp_session = create_cached_session(
    http_cache=http_cache,
    cache_manager_name=cache_manager_name
)
```

**Issues identified:**
- Session lifecycle managed manually in each caller
- Caching configuration passed redundantly
- No session reuse across operations
- Tests must mock `create_cached_session` in multiple locations

## Protocol Definition

### HttpClientProtocol

```python
from typing import Protocol
import requests

class HttpClientProtocol(Protocol):
    """
    Protocol for HTTP client operations.
    
    Defines the contract for HTTP clients that can perform
    requests. Implementations can be real clients, mocks,
    or stub implementations for testing.
    """
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Perform GET request.
        
        Args:
            url: Target URL.
            **kwargs: Additional request parameters.
            
        Returns:
            HTTP response object.
        """
        ...
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """
        Perform POST request.
        
        Args:
            url: Target URL.
            **kwargs: Additional request parameters.
            
        Returns:
            HTTP response object.
        """
        ...
    
    def close(self) -> None:
        """
        Close the HTTP client and release resources.
        """
        ...
    
    @property
    def session(self) -> requests.Session:
        """Access underlying session for advanced operations."""
        ...
```

### HttpClientProvider Class

```python
import requests
from pathlib import Path
from typing import Any

class HttpClientProvider:
    """
    Abstraction for HTTP client creation and management.
    
    Wraps session creation with caching, providing a consistent
    interface for HTTP operations throughout the application.
    """
    
    def __init__(
        self,
        cache_manager_name: str = "default",
        cache_manager: CacheManager | None = None,
        http_cache: HttpCacheConfig | None = None
    ) -> None:
        """
        Initialize HTTP client provider.
        
        Args:
            cache_manager_name: Name of cache manager to use.
            cache_manager: Optional pre-configured cache manager.
            http_cache: Optional HTTP cache configuration.
        """
        self._cache_manager_name = cache_manager_name
        self._cache_manager = cache_manager
        self._http_cache = http_cache
        self._session: requests.Session | None = None
    
    @property
    def session(self) -> requests.Session:
        """
        Get or create HTTP session with caching.
        
        Sessions are cached and reused across multiple calls.
        
        Returns:
            Configured requests.Session with caching.
        """
        if self._session is None:
            self._session = self._create_session()
        return self._session
    
    def _create_session(self) -> requests.Session:
        """Create new cached session."""
        if self._cache_manager is not None:
            return create_cached_session(
                cache_manager_name=self._cache_manager.name,
                http_cache=self._http_cache
            )
        else:
            return create_cached_session(
                cache_manager_name=self._cache_manager_name,
                http_cache=self._http_cache
            )
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Perform GET request.
        
        Args:
            url: Target URL.
            **kwargs: Additional request parameters.
            
        Returns:
            HTTP response.
        """
        return self.session.get(url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """
        Perform POST request.
        
        Args:
            url: Target URL.
            **kwargs: Additional request parameters.
            
        Returns:
            HTTP response.
        """
        return self.session.post(url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """Perform PUT request."""
        return self.session.put(url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """Perform DELETE request."""
        return self.session.delete(url, **kwargs)
    
    def head(self, url: str, **kwargs) -> requests.Response:
        """Perform HEAD request."""
        return self.session.head(url, **kwargs)
    
    def close(self) -> None:
        """Close session and release resources."""
        if self._session is not None:
            self._session.close()
            self._session = None
    
    def __enter__(self) -> "HttpClientProvider":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()
```

## Testing Implementations

### MockHttpClient

```python
from unittest.mock import Mock
import requests

class MockHttpClient:
    """
    Mock HTTP client for testing.
    
    Records all requests made and returns configurable responses.
    """
    
    def __init__(self) -> None:
        """Initialize with empty request history."""
        self.requests: list[tuple[str, str, dict]] = []
        self._responses: dict[str, requests.Response] = {}
        self._default_response: requests.Response | None = None
    
    def mock_response(
        self,
        method: str,
        url: str,
        response_text: str = "",
        status_code: int = 200,
        headers: dict | None = None
    ) -> None:
        """
        Configure mock response for specific request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to match
            response_text: Response body text
            status_code: HTTP status code
            headers: Response headers
        """
        mock_resp = Mock(spec=requests.Response)
        mock_resp.text = response_text
        mock_resp.status_code = status_code
        mock_resp.headers = headers or {}
        mock_resp.json = lambda: {}  # Override as needed
        mock_resp.raise_for_status = Mock()
        
        key = f"{method.upper()}:{url}"
        self._responses[key] = mock_resp
    
    def mock_default_response(
        self,
        response_text: str = "",
        status_code: int = 200,
        headers: dict | None = None
    ) -> None:
        """
        Configure default response for unmatched requests.
        
        Args:
            response_text: Default response body text
            status_code: Default HTTP status code
            headers: Default response headers
        """
        mock_resp = Mock(spec=requests.Response)
        mock_resp.text = response_text
        mock_resp.status_code = status_code
        mock_resp.headers = headers or {}
        mock_resp.json = lambda: {}
        mock_resp.raise_for_status = Mock()
        self._default_response = mock_resp
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Record and return mock GET response."""
        self.requests.append(("GET", url, kwargs))
        return self._get_response("GET", url)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """Record and return mock POST response."""
        self.requests.append(("POST", url, kwargs))
        return self._get_response("POST", url)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        """Record and return mock PUT response."""
        self.requests.append(("PUT", url, kwargs))
        return self._get_response("PUT", url)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        """Record and return mock DELETE response."""
        self.requests.append(("DELETE", url, kwargs))
        return self._get_response("DELETE", url)
    
    def head(self, url: str, **kwargs) -> requests.Response:
        """Record and return mock HEAD response."""
        self.requests.append(("HEAD", url, kwargs))
        return self._get_response("HEAD", url)
    
    def _get_response(self, method: str, url: str) -> requests.Response:
        """Get mock response for request."""
        key = f"{method.upper()}:{url}"
        if key in self._responses:
            return self._responses[key]
        if self._default_response is not None:
            return self._default_response
        # Return default 200 OK if nothing configured
        mock_resp = Mock(spec=requests.Response)
        mock_resp.text = ""
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json = lambda: {}
        mock_resp.raise_for_status = Mock()
        return mock_resp
    
    def close(self) -> None:
        """Reset mock state."""
        self.requests.clear()
        self._responses.clear()
        self._default_response = None
    
    @property
    def session(self) -> Mock:
        """Return mock session for compatibility."""
        return Mock()
```

## Integration Patterns

### With ServiceContainer

```python
class ServiceContainer:
    """Extended to include HTTP client provider."""
    
    def get_http_client(self) -> HttpClientProvider:
        """Get HTTP client provider."""
        return HttpClientProvider(
            cache_manager_name=self._name,
            cache_manager=self.cache_manager
        )
```

### With Source Classes

Current (tight coupling):

```python
class WhatTheSpecSource(TDocSource):
    def __init__(
        self,
        config: TDocSourceConfig,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.session = session  # Must be provided or None
```

Proposed (protocol-based):

```python
class WhatTheSpecSource(TDocSource):
    def __init__(
        self,
        config: TDocSourceConfig,
        http_client: HttpClientProtocol | None = None,
    ) -> None:
        self.config = config
        self._http_client = http_client
    
    @property
    def http_client(self) -> HttpClientProtocol:
        """Get HTTP client, creating if needed."""
        if self._http_client is None:
            self._http_client = HttpClientProvider()
        return self._http_client
    
    def fetch_by_id(self, tdoc_id: str) -> TDocMetadata:
        """Fetch TDoc metadata."""
        response = self.http_client.get(
            f"https://api.whatthespec.net/tdoc/{tdoc_id}"
        )
        return self._parse_response(response)
```

## Usage Examples

### Production Usage

```python
# Using container
container = ServiceContainer(cache_dir)
client = container.get_http_client()

try:
    response = client.get("https://api.whatthespec.net/tdoc/R1-2400001")
    data = response.json()
finally:
    client.close()

# Using context manager
with HttpClientProvider() as client:
    response = client.get(url)
    # Auto-closed on exit
```

### Test Usage

```python
def test_whatthespec_fetch():
    """Test TDoc fetching with mock HTTP client."""
    # Setup mock
    mock_client = MockHttpClient()
    mock_client.mock_response(
        "GET",
        "https://api.whatthespec.net/tdoc/R1-2400001",
        response_text='{"id": "R1-2400001", "title": "Test"}',
        status_code=200
    )
    
    # Test source with mock
    source = WhatTheSpecSource(config, http_client=mock_client)
    result = source.fetch_by_id("R1-2400001")
    
    # Verify
    assert result.id == "R1-2400001"
    assert len(mock_client.requests) == 1
    assert mock_client.requests[0] == ("GET", "https://api.whatthespec.net/tdoc/R1-2400001", {})
```

### Mock with Expected Requests

```python
def test_source_makes_expected_calls():
    """Verify source makes expected HTTP calls."""
    mock_client = MockHttpClient()
    
    # Setup expected responses
    mock_client.mock_response("GET", "https://api.whatthespec.net/tdoc/R1-2400001")
    mock_client.mock_response("GET", "https://api.whatthespec.net/tdoc/R1-2400002")
    
    source = WhatTheSpecSource(config, http_client=mock_client)
    
    # Execute
    source.fetch_multiple(["R1-2400001", "R1-2400002"])
    
    # Verify all expected calls were made
    assert len(mock_client.requests) == 2
```

## Backward Compatibility

```python
# Existing code continues to work
with create_cached_session() as session:
    response = session.get(url)

# New code can use provider
provider = HttpClientProvider()
try:
    response = provider.get(url)
finally:
    provider.close()

# Even newer code can use container
container = ServiceContainer()
client = container.get_http_client()
try:
    response = client.get(url)
finally:
    container.close()
```

## Error Handling

```python
def safe_http_request(provider: HttpClientProvider, url: str):
    """Example of error handling with HTTP provider."""
    try:
        response = provider.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection failed for {url}")
        return None
    except requests.exceptions.Timeout:
        logger.warning(f"Request timeout for {url}")
        return None
    finally:
        provider.close()
```

## Related Documents

- [ServiceContainer Interface](service-container.md)
- [DatabaseFactory Protocol](database-factory.md)
- [Testability Approach](testability.md)
- [Error Handling Approach](error-handling.md)
