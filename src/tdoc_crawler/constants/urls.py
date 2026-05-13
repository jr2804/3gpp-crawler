"""URL templates and base URLs for 3GPP resources."""

from __future__ import annotations

from typing import Final

PORTAL_BASE_URL: Final[str] = "https://portal.3gpp.org"

MEETINGS_REST_URL: Final[str] = f"{PORTAL_BASE_URL}/webservices/Rest/Meetings.svc/GetMeetings"
TDOC_VIEW_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/CreateTdoc.Aspx"
TDOC_DOWNLOAD_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/DownloadTDoc.aspx"
LOGIN_URL: Final[str] = f"{PORTAL_BASE_URL}/login.aspx"

SPEC_URL_TEMPLATE: Final[str] = "https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}"

# Common browser headers to avoid 403 Forbidden responses
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

__all__ = [
    "LOGIN_URL",
    "MEETINGS_REST_URL",
    "PORTAL_BASE_URL",
    "SPEC_URL_TEMPLATE",
    "TDOC_DOWNLOAD_URL",
    "TDOC_VIEW_URL",
]
