---
name: 3gpp-portal-authentication
description: EOL authentication, AJAX login patterns, 3GPP portal data fetching, and session management. Use when accessing protected 3GPP portal resources that require EOL login, fetching TDoc metadata, or working with 3GPP portal APIs.
metadata:
  related: [3gpp-tdocs, 3gpp-meetings, 3gpp-specifications, 3gpp-change-request]
---

# 3GPP Portal Authentication

## Overview

The 3GPP portal (<https://portal.3gpp.org/>) provides access to protected resources that require ETSI Online Account (EOL) authentication.

### Authentication Requirements

- **EOL Account**: ETSI Online Account username and password
- **Protected Resources**: Meeting registration, certain meeting documents, 3GU portal features
- **Public Resources**: TDoc files on FTP/HTTP server, specifications, and most meeting information do NOT require authentication

## EOL Account

### What is EOL?

ETSI Online Account is the authentication system for accessing ETSI and 3GPP services.

### When is EOL Required?

**Required for:**

- Meeting registration and check-in
- 3GU Portal full access
- Protected meeting documents

**NOT required for:**

- Public TDoc files on FTP/HTTP server
- Public meeting lists and calendars
- Specification downloads
- TDoc metadata viewing (basic metadata may be public)

## Portal Authentication Flow

### AJAX-Based Login (Legacy/Current)

The 3GPP portal uses JavaScript-based AJAX login via `LoginEOL.ashx` endpoint.

### Login Process

1. **Session Establishment**: Visit login page to establish session cookies
1. **AJAX Request**: POST to `LoginEOL.ashx` with credentials
1. **Session Validation**: Parse JSON response for authentication status

### Code Pattern

```python
import requests
from bs4 import BeautifulSoup

session = requests.Session()

# 1. Visit login page to establish session
login_page = session.get("https://portal.3gpp.org/")
login_page.raise_for_status()

# 2. AJAX login
login_payload = {
    "username": eol_username,
    "password": eol_password,
}

response = session.post(
    "https://portal.3gpp.org/ngppapp/LoginEOL.ashx",
    data=login_payload
)

# 3. Parse response
auth_result = response.json()
if auth_result.get("success", False):
    raise PortalAuthenticationError(f"EOL authentication failed: {auth_result}")
```

### PortalSession Class

`PortalSession` manages authenticated HTTP sessions with 3GPP portal:

**Key Methods:**

- `authenticate()`: Performs EOL login using AJAX
- `get_tdoc_metadata(tdoc_id)`: Fetches TDoc metadata with auto-authentication
- `_ensure_authenticated()`: Validates session before protected requests

**Implementation Pattern:**

```python
class PortalSession:
    def __init__(self, credentials: PortalCredentials, timeout: int = 30):
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()
        self._authenticated = False

    def authenticate(self) -> None:
        # 1. Visit login page to establish session
        response = self.session.get("https://portal.3gpp.org/", timeout=self.timeout)
        response.raise_for_status()

        # 2. AJAX login
        payload = {
            "username": self.credentials.username,
            "password": self.credentials.password,
        }
        response = self.session.post(
            "https://portal.3gpp.org/ngppapp/LoginEOL.ashx",
            json=payload,
            timeout=self.timeout
        )

        # 3. Parse response
        auth_result = response.json()
        if auth_result.get("success", False):
            raise PortalAuthenticationError(
                f"EOL authentication failed: {auth_result}"
            )

        self._authenticated = True

    def get_tdoc_metadata(self, tdoc_id: str) -> dict[str, str]:
        """Fetch TDoc metadata from portal page.

        URL: https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid={tdoc_id}
        """
        self._ensure_authenticated()

        # Fetch portal page
        url = f"https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid={tdoc_id}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        metadata = {}
        for label in soup.find_all("label"):
            value_element = label.find_next_sibling("input")
            if value_element and value_element.get("value"):
                field_name = label.get_text().strip(": ").lower()
                metadata[field_name] = value_element.get("value")

        return metadata

    def _ensure_authenticated(self) -> None:
        """Ensure session is authenticated before making protected requests."""
        if not self._authenticated:
            raise PortalAuthenticationError(
                "Session not authenticated. Call authenticate() first."
            )
```

## Exception Handling

### PortalAuthenticationError

Raised when EOL login fails.

```python
class PortalAuthenticationError(Exception):
    """Raised when 3GPP portal authentication fails."""
    pass
```

### PortalParsingError

Raised when portal page parsing fails.

```python
class PortalParsingError(Exception):
    """Raised when portal page HTML parsing fails."""
    pass
```

## Credentials Handling

### PortalCredentials Model

```python
from pydantic import BaseModel

class PortalCredentials(BaseModel):
    """3GPP portal authentication credentials."""
    username: str
    password: str
```

### Public Functions

### fetch_tdoc_metadata

Wrapper function for TDoc metadata fetching with automatic authentication:

```python
from tdoc_crawler.crawlers import fetch_tdoc_metadata
from tdoc_crawler.models import PortalCredentials

credentials = PortalCredentials(username="user", password="pass")
metadata = fetch_tdoc_metadata("R1-2301234", credentials)
# Returns: {"title": "...", "meeting": "...", ...}
```

## Usage Patterns

### When Authentication is Required

**Meeting Registration:**

```python
session = PortalSession(credentials)
session.authenticate()
# Now access protected meeting registration pages
```

**3GU Portal Access:**

```python
from tdoc_crawler.crawlers import PortalSession
from tdoc_crawler.models import PortalCredentials

session = PortalSession(credentials)
session.authenticate()

# Access 3GU portal features requiring login
```

### When Authentication is NOT Required

**Public TDoc Access:**

```python
# Direct HTTP access to FTP server
import requests
session = requests.Session()
response = session.get("https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/R1-2301234.zip")
# No authentication needed
```

**TDoc Metadata (public):**

```python
# Basic TDoc metadata may be publicly viewable without login
# Full metadata including contact info requires EOL account
```

## Key Implementation Points

### AJAX Endpoint

- **URL**: `https://portal.3gpp.org/ngppapp/LoginEOL.ashx`
- **Method**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **Request Body**: Form-encoded with `username` and `password` fields
- **Response**: JSON with `success` boolean

### Session Management

- **Cookies**: Session cookies maintained automatically by `requests.Session`
- **Timeout**: Default 30 seconds
- **Retry Logic**: No automatic retry (application-level authentication)

### Error Handling

- **401 Unauthorized**: Invalid credentials or session expired
- **500 Internal Server**: 3GPP portal temporarily unavailable
- **Network Timeout**: Request took too long

## Best Practices

1. **Check authentication requirement** before attempting protected operations
1. **Use session context** to maintain authentication state
1. **Handle auth failures** gracefully with clear error messages
1. **Don't cache credentials** in code or environment files
1. **Use environment variables** (`EOL_USERNAME`, `EOL_PASSWORD`) for credentials

## Cross-References

- **@3gpp-tdocs** - TDoc metadata structure and portal URLs
- **@3gpp-meetings** - Meeting registration and portal integration
- **@3gpp-specifications** - Spec file access patterns

## Resources

- 3GPP Portal: <https://portal.3gpp.org/>
- 3GPP Official: <https://www.3gpp.org/>
- ETSI Portal: <https://portal.etsi.org/>
- Login documentation: <https://www.3gpp.org/delegates-corner/>

## Notes

- The AJAX login mechanism is specific to 3GPP portal
- 3GU Portal uses same authentication system
- Meeting registration requires EOL account
- Most TDoc-related operations do NOT require authentication
- Consider using `PortalSession` class pattern for production code
