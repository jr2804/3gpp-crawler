"""Portal REST API source for meeting metadata.

Uses ``/webservices/Rest/Meetings.svc/GetMeetings`` to fetch structured
meeting data as JSON, replacing the legacy dynareport HTML scraping.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

import niquests
from pydantic import ValidationError

from tdoc_crawler.constants.urls import MEETING_PORTAL_URL_TEMPLATE, MEETINGS_REST_URL, PORTAL_BASE_URL
from tdoc_crawler.database.oxyde_models import MeetingMetadata
from tdoc_crawler.meetings.models import PortalMeeting
from tdoc_crawler.models.subworking_groups import SUBWORKING_GROUP_RECORDS
from tdoc_crawler.utils.json_types import coerce_json_value

# Parent TBIDs for the 3 TSGs — used with IncludeChildTbs=True to get
# all child WG meetings in fewer API calls.
_TSG_PARENT_TBIDS: list[int] = [373, 375, 649]  # RAN, SA, CT

# Map SubTB → (tbid, code) for reverse lookup from API TBId field
_SUBTB_TO_WG: dict[int, tuple[int, str]] = {r.subtb: (r.tbid, r.code) for r in SUBWORKING_GROUP_RECORDS}

# Map code → subtb
_CODE_TO_SUBTB: dict[str, int] = {r.code: r.subtb for r in SUBWORKING_GROUP_RECORDS}

_PAGE_SIZE = 500

DEFAULT_START_DATE = date(1994, 1, 1)
DEFAULT_END_DATE = date.today() + timedelta(days=365 * 3)  # 3 years in the future, to include upcoming meetings

logger = logging.getLogger(__name__)


def fetch_meetings(
    subgroups: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    timeout: float = 60,
) -> list[MeetingMetadata]:
    """Fetch meeting metadata from the 3GPP portal REST API.

    Paginates automatically through all results.

    Args:
        subgroups: Optional subgroup codes (e.g. ``["S4", "R1"]``).
            If None, fetches all working groups.
        start_date: Inclusive start date filter.  Defaults to 1994-01-01.
        end_date: Inclusive end date filter.  Defaults to 2030-12-31.
        timeout: HTTP request timeout in seconds.

    Returns:
        List of parsed MeetingMetadata objects.
    """
    tbs = _build_subtb_filter(subgroups)
    # When specific subgroups are given, do NOT expand to child TBs —
    # otherwise plenary codes like SP (subtb=375 == SA tbid) pull in all
    # SA subgroup meetings when IncludeChildTbs=True.
    include_children = not subgroups

    sd = (start_date or DEFAULT_START_DATE).strftime("%Y-%m-%d 00:00:00")
    ed = (end_date or DEFAULT_END_DATE).strftime("%Y-%m-%d 23:59:59")

    all_meetings: list[MeetingMetadata] = []
    start_row = 0

    # Use a plain session — the cached session (hishel) doesn't handle
    # POST endpoints with JSON bodies correctly.
    session = niquests.Session(disable_http3=True)
    try:
        while True:
            payload = {
                "getMeetingsInput": {
                    "StartRow": start_row,
                    "ResultsPerPage": _PAGE_SIZE,
                    "IncludeChildTbs": include_children,
                    "IncludeNonTBMeetings": False,
                    "Tbs": tbs,
                    "StartDate": sd,
                    "EndDate": ed,
                }
            }
            try:
                r = session.post(
                    MEETINGS_REST_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout,
                )
                r.raise_for_status()
            except Exception as exc:
                logger.error("Portal meetings API request failed: %s", exc)
                break

            try:
                payload = coerce_json_value(r.json())
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.error(
                    "Portal meetings API returned invalid JSON (status=%d, body=%s): %s",
                    r.status_code,
                    r.text[:200],
                    exc,
                )
                break

            if not payload:
                break

            if not isinstance(payload, list):
                logger.error("Portal meetings API returned %s instead of a list", type(payload).__name__)
                break

            for entry in payload:
                try:
                    meeting = PortalMeeting.model_validate(entry)
                except ValidationError as exc:
                    logger.warning("Skipping malformed portal meeting entry: %s", exc)
                    continue
                all_meetings.append(_portal_meeting_to_metadata(meeting))

            logger.debug(
                "Portal meetings page start_row=%d: %d results (total: %d)",
                start_row,
                len(payload),
                len(all_meetings),
            )

            if len(payload) < _PAGE_SIZE:
                break
            start_row += _PAGE_SIZE
    finally:
        session.close()

    return all_meetings


def _build_subtb_filter(subgroups: list[str] | None) -> list[int]:
    """Convert subgroup codes to SubTB IDs for the API ``Tbs`` parameter.

    If *subgroups* is empty/None, returns the 3 TSG parent TBIDs so that
    ``IncludeChildTbs=True`` fetches all WGs.
    """
    if not subgroups:
        return list(_TSG_PARENT_TBIDS)
    result: list[int] = []
    for code in subgroups:
        subtb = _CODE_TO_SUBTB.get(code.upper())
        if subtb is not None:
            result.append(subtb)
        else:
            logger.warning("Unknown subgroup code %r — skipping", code)
    return result or list(_TSG_PARENT_TBIDS)


def _portal_meeting_to_metadata(m: PortalMeeting) -> MeetingMetadata:
    """Convert a single portal API meeting object to MeetingMetadata."""
    subtb = m.subtb
    wg_info = _SUBTB_TO_WG.get(subtb) if subtb else None
    tbid = wg_info[0] if wg_info else subtb or 0

    return MeetingMetadata(
        meeting_id=m.meeting_id,
        tbid=tbid,
        subtb=subtb,
        short_name=m.short_title,
        title=m.title,
        start_date=_parse_portal_date(m.start_date),
        end_date=_parse_portal_date(m.end_date),
        location=m.location or None,
        files_url=m.files_url or None,
        portal_url=MEETING_PORTAL_URL_TEMPLATE.format(portal_base=PORTAL_BASE_URL, meeting_id=m.meeting_id),
        tdoc_count=m.doc_count,
    )


def _parse_portal_date(text: str | None) -> date | None:
    """Parse portal datetime string ``'YYYY-MM-DD HH:MM:SS'`` → date."""
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except (ValueError, IndexError):
        return None


__all__ = ["fetch_meetings"]
