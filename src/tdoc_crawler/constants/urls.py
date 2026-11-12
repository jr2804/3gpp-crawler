"""URL templates and base URLs for 3GPP resources."""

from __future__ import annotations

from typing import Final

PORTAL_BASE_URL: Final[str] = "https://portal.3gpp.org"

MEETINGS_REST_URL: Final[str] = f"{PORTAL_BASE_URL}/webservices/Rest/Meetings.svc/GetMeetings"
TDOC_VIEW_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/CreateTdoc.Aspx"
TDOC_DOWNLOAD_URL: Final[str] = f"{PORTAL_BASE_URL}/ngppapp/DownloadTDoc.aspx"
LOGIN_URL: Final[str] = f"{PORTAL_BASE_URL}/login.aspx"

SPEC_URL_TEMPLATE: Final[str] = "https://www.3gpp.org/ftp/Specs/archive/{series}/{normalized}/{file_name}"
SPEC_DYNAREPORT_URL_TEMPLATE: Final[str] = "https://www.3gpp.org/dynareport/{compact}.htm"
DYNAREPORT_URL_TEMPLATE: Final[str] = "https://www.3gpp.org/dynareport?code={code}"
WORK_ITEM_DETAILS_URL_TEMPLATE: Final[str] = f"{PORTAL_BASE_URL}/desktopmodules/WorkItem/WorkItemDetails.aspx?workitemId={{uid}}"
DOCLIST_URL_TEMPLATE: Final[str] = "{portal_base}/ngppapp/GenerateDocumentList.aspx?meetingId={meeting_id}"
MEETING_PORTAL_URL_TEMPLATE: Final[str] = "{portal_base}/Home.aspx#/meeting?MtgId={meeting_id}"
WHATSPEC_BASE_URL: Final[str] = "https://whatthespec.net"
WHATSPEC_TDOC_URL_TEMPLATE: Final[str] = "{base}/3gpp/tdoc.php?name={tdoc_id}&api=1"
WHATSPEC_SPEC_URL_TEMPLATE: Final[str] = "{base}/3gpp/spec.php?q={compact}&api=1"

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
    "DOCLIST_URL_TEMPLATE",
    "DYNAREPORT_URL_TEMPLATE",
    "LOGIN_URL",
    "MEETINGS_REST_URL",
    "MEETING_PORTAL_URL_TEMPLATE",
    "PORTAL_BASE_URL",
    "SPEC_DYNAREPORT_URL_TEMPLATE",
    "SPEC_URL_TEMPLATE",
    "TDOC_DOWNLOAD_URL",
    "TDOC_VIEW_URL",
    "WHATSPEC_BASE_URL",
    "WHATSPEC_SPEC_URL_TEMPLATE",
    "WHATSPEC_TDOC_URL_TEMPLATE",
    "WORK_ITEM_DETAILS_URL_TEMPLATE",
]
