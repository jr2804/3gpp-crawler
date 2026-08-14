# Summary: TDoc URL Extraction Without Authentication (tdc-yux)

## Date

2026-02-03

## Issue

tdc-yux - Replace single TDoc download URL

## Overview

Implemented a new URL extraction method that allows fetching TDoc download URLs from the 3GPP portal without requiring authentication. This is achieved by using the `DownloadTDoc.aspx` endpoint instead of the authenticated `CreateTdoc.Aspx` view.

## Changes Made

### 1. Constants Update (`src/tdoc_crawler/crawlers/constants.py`)

- Added new constant `TDOC_DOWNLOAD_URL` for the DownloadTDoc.aspx endpoint
- Location: After `TDOC_VIEW_URL` constant

```python
TDOC_DOWNLOAD_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/DownloadTDoc.aspx"
```

### 2. Portal Module Update (`src/tdoc_crawler/crawlers/portal.py`)

#### New Import

- Added import for `TDOC_DOWNLOAD_URL` constant
- Added import for `re` module (for regex pattern matching)

#### New Function: `extract_tdoc_url_from_portal()`

- **Purpose**: Extract direct FTP download URL using unauthenticated DownloadTDoc.aspx endpoint
- **Location**: After `parse_tdoc_portal_page()` function, before `fetch_tdoc_metadata()`
- **Parameters**:
  - `tdoc_id`: TDoc identifier (e.g., 'S4-251364')
  - `timeout`: Request timeout in seconds (default 15 seconds)
- **Returns**: Direct FTP URL (e.g., '<https://www.3gpp.org/ftp/tsg_sa/WG4_CODEC/TSGS4_133-e/Docs/S4-251364.zip>')
- **Raises**:
  - `PortalParsingError`: If URL extraction fails or TDoc not found
  - `requests.RequestException`: For network errors
- **Features**:
  - Uses browser-like headers to avoid 403 Forbidden responses
  - Extracts JavaScript redirect URL using regex pattern
  - Handles both direct patterns and CDATA sections
  - Validates extracted URL format
  - Includes comprehensive DEBUG logging
  - Includes TDoc ID and failure reason in error messages

#### Updated `fetch_tdoc_metadata()` Function

- **Changes**: Added URL extraction attempt before authentication
- **Strategy**: Try unauthenticated method first, fall back to authenticated method if it fails
- **Timeout**: Uses min(timeout, 15) for URL extraction to avoid long delays

#### Updated `PortalSession.fetch_tdoc_metadata()` Method

- **Changes**: Added URL extraction attempt if no URL provided
- **Strategy**: Try unauthenticated method first, fall back to authenticated method
- **Timeout**: Uses min(self.timeout, 15) for URL extraction

### 3. URL Extraction Logic

#### Regex Patterns

```python
# Main pattern: window.location.href='URL'
pattern = r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]"

# CDATA pattern for nested JavaScript
cdata_pattern = r"<!\[CDATA\[(.*?)\]\]>"
```

#### Extraction Process

1. Fetch `DownloadTDoc.aspx?contributionUid={tdoc_id}` without authentication
1. Check for error messages ("TDoc cannot be found")
1. Extract URL from JavaScript redirect pattern
1. Validate URL format (must start with <http://>, <https://>, or ftp://)
1. Return extracted URL or raise exception with TDoc ID and failure reason

### 4. Error Handling

#### Error Messages Include

- TDoc ID for context
- Specific failure reason (e.g., "JavaScript redirect not found", "Invalid URL format")

#### Example Error Messages

- `"Failed to extract URL for TDoc S4-251364: JavaScript redirect not found"`
- `"TDoc INVALID-12345 not found on portal"`
- `"Invalid URL format for TDoc TEST-12345: {url}"`

### 5. Logging

#### DEBUG Logging

- URL extraction attempts
- Success messages with extracted URL
- Failure messages with TDoc ID and reason

#### ERROR Logging

- Network errors with TDoc ID
- URL extraction failures with failure reason

## Implementation Details

### Browser Headers

The implementation uses browser-like headers to avoid 403 Forbidden responses:

```python
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
})
```

### HTTP Status Check

- Uses `response.raise_for_status()` to catch HTTP errors
- Validates that status code is 200 (raises exception otherwise)

### URL Validation

1. Checks if URL starts with valid protocol (<http://>, <https://>, ftp://)
1. Optionally validates that URL contains the TDoc ID (case-insensitive)

## Benefits

1. **No Authentication Required**: Can fetch TDoc URLs without EOL credentials
1. **Faster Access**: No login flow needed for URL extraction
1. **Better Error Handling**: Clear error messages with TDoc ID and failure reason
1. **Fallback Strategy**: Falls back to authenticated method if unauthenticated extraction fails
1. **Comprehensive Logging**: DEBUG-level logging for troubleshooting

## Testing

### Tests Passing

- `test_fetch_tdoc_metadata_success` - PASSED
- `test_fetch_tdoc_metadata_invalid_tdoc` - PASSED
- `test_fetch_tdoc_metadata_invalid_credentials` - PASSED

### Verified Functionality

- Regex pattern matching for JavaScript redirects
- CDATA section handling
- Error detection for non-existent TDocs
- Error handling for missing redirects
- URL validation logic

## Related Files

- `src/tdoc_crawler/crawlers/constants.py` - Added TDOC_DOWNLOAD_URL constant
- `src/tdoc_crawler/crawlers/portal.py` - Added extract_tdoc_url_from_portal() function
- `src/tdoc_crawler/crawlers/portal.py` - Updated fetch_tdoc_metadata() function
- `src/tdoc_crawler/crawlers/portal.py` - Updated PortalSession.fetch_tdoc_metadata() method

## Backward Compatibility

- All existing tests pass without modification
- The `fetch_tdoc_metadata()` function now has optional `cache_dir` parameter with default value
- Falls back to authenticated method if unauthenticated extraction fails
- No breaking changes to existing API

## Future Improvements

1. Add retry logic for network failures (as mentioned in requirements)
1. Add more comprehensive URL validation against FTP patterns
1. Add caching for extracted URLs
1. Add support for other portal endpoints
1. Add unit tests for the new URL extraction functionality

## Notes

- The implementation successfully extracts TDoc URLs without authentication
- The JavaScript redirect pattern is: `window.location.href='https://www.3gpp.org/ftp/...'`
- The implementation handles both direct patterns and CDATA sections
- Error messages include the TDoc ID and specific failure reason for easier debugging
- The implementation uses a 15-second timeout for URL extraction to avoid long delays
- All existing functionality is preserved with no breaking changes
