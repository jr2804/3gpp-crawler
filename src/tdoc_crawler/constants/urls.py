"""URL templates and base URLs for 3GPP resources."""

from __future__ import annotations

from typing import Final

MEETINGS_BASE_URL: Final[str] = "https://www.3gpp.org/dynareport?code=Meetings-{code}.htm"
PORTAL_BASE_URL: Final[str] = "https://portal.3gpp.org"
TDOC_VIEW_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/CreateTdoc.Aspx"
TDOC_DOWNLOAD_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/DownloadTDoc.aspx"
LOGIN_URL: Final[str] = f"{PORTAL_BASE_URL}/login.aspx"

SPEC_URL_TEMPLATE: Final[str] = "https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}"

__all__ = [
    "LOGIN_URL",
    "MEETINGS_BASE_URL",
    "PORTAL_BASE_URL",
    "SPEC_URL_TEMPLATE",
    "TDOC_DOWNLOAD_URL",
    "TDOC_VIEW_URL",
]
