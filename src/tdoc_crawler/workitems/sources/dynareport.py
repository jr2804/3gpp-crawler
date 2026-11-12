"""DynaReport work item sources: the public 3gpp.org work item pages.

The 3GPP website publishes work item lists as static DynaReport pages that
need no login:

- ``TSG-WG--<WG>--wis.htm`` — work items per lead body (working group). This
  list is current: it contains in-flight work items that the global list lags
  behind. Used to build the catalogue.
- ``WI-List.htm`` — one global table of all work items (lags behind for
  work items whose specifications are not published yet). Used to discover
  the set of lead bodies and for the manual completeness check.
- ``WiSpec--<UID>.htm`` / ``WiCr--<UID>.htm`` — specifications and change
  requests of one work item.
- ``WorkItemDetails.aspx?workitemId=<UID>`` — portal details page with
  status, WI level and the parent/child hierarchy.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final

import niquests as requests
from bs4 import BeautifulSoup, Tag

from tdoc_crawler.config.settings import HttpConfig
from tdoc_crawler.constants.urls import DYNAREPORT_URL_TEMPLATE, WORK_ITEM_DETAILS_URL_TEMPLATE
from tdoc_crawler.http_client import create_cached_session
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.normalization import normalize_spec_number
from tdoc_crawler.workitems.models import WorkItem, WorkItemCr, WorkItemDetails

WORK_ITEM_LIST_CODE: Final[str] = "WI-List"

# Title prefixes on the per-working-group lists encode the WI level.
_LEVEL_PREFIXES: Final[dict[str, int]] = {
    "feature or study item:": 1,
    "building block:": 2,
    "work task:": 3,
}
_WORK_ITEM_UID_LINK = re.compile(r"workitemId=(\d+)", re.IGNORECASE)
_WG_LIST_LINK = re.compile(r"TSG-WG--([A-Za-z0-9]+)--wis\.htm", re.IGNORECASE)
_ORDINAL_LEVEL = re.compile(r"(\d+)(?:st|nd|rd|th)\s+level", re.IGNORECASE)
_SPEC_HREF = re.compile(r"/DynaReport/([0-9]+[A-Za-z]?)\.htm", re.IGNORECASE)
_PLACEHOLDER_TEXTS = frozenset({"-", "", "none", "no data available for the current query."})

_logger = get_logger(__name__)


class WorkItemSourceError(RuntimeError):
    """Raised when a work item page cannot be fetched or parsed."""


def discover_lead_bodies(
    *,
    timeout: int = 120,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    session: requests.Session | None = None,
) -> list[str]:
    """Discover the lead body codes from the global work item list."""
    html = _fetch_html(
        work_item_list_url(),
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        session=session,
    )
    lead_bodies = parse_lead_bodies(html)
    if not lead_bodies:
        msg = "The global work item list references no per-working-group pages"
        raise WorkItemSourceError(msg)
    return lead_bodies


# ---------------------------------------------------------------------------
# Parsing (pure functions over HTML, unit-testable without network)


def parse_lead_bodies(html: str) -> list[str]:
    """Extract the lead body codes referenced by a DynaReport page."""
    return sorted({match.group(1).upper() for match in _WG_LIST_LINK.finditer(html)})


def fetch_work_items(
    wg_codes: Sequence[str],
    *,
    timeout: int = 60,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, list[WorkItem]]:
    """Fetch the work item lists of several lead bodies over one session.

    Args:
        wg_codes: Lead body codes (e.g. ``"S4"``, ``"SP"``, ``"GP"``)
        timeout: Request timeout in seconds
        http_config: Optional HTTP configuration
        http_cache_file: Optional explicit HTTP cache database
        progress: Optional callable invoked with each completed code

    Returns:
        Mapping of lead body code to its work items, in input order

    Raises:
        WorkItemSourceError: If any page cannot be fetched or parsed
    """
    results: dict[str, list[WorkItem]] = {}
    with work_item_session(http_config=http_config, http_cache_file=http_cache_file) as session:
        for code in wg_codes:
            results[code] = fetch_wg_work_items(
                code,
                timeout=timeout,
                http_config=http_config,
                http_cache_file=http_cache_file,
                session=session,
            )
            if progress is not None:
                progress(code)
    return results


@contextmanager
def work_item_session(
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
) -> Generator[requests.Session]:
    """Yield a cached HTTP session for the work item pages."""
    session = create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    try:
        yield session
    finally:
        session.close()


def fetch_wg_work_items(
    wg_code: str,
    *,
    timeout: int = 60,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    session: requests.Session | None = None,
) -> list[WorkItem]:
    """Fetch and parse the work item list of one lead body."""
    html = _fetch_html(
        wg_work_items_url(wg_code),
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        session=session,
    )
    work_items = parse_wg_work_items(html, lead_body=wg_code)
    if not work_items:
        _logger.warning("Work item list for %s carries no work items (unknown code?)", wg_code)
    return work_items


def wg_work_items_url(wg_code: str) -> str:
    """Return the URL of the per-working-group work item list."""
    return DYNAREPORT_URL_TEMPLATE.format(code=f"TSG-WG--{wg_code.strip().upper()}--wis.htm")


def parse_wg_work_items(html: str, lead_body: str) -> list[WorkItem]:
    """Parse a per-working-group work item list into work items.

    Rows carry three cells: the title links to ``WorkItemDetails.aspx?
    workitemId=<UID>`` (prefixed with the WI level), the second cell holds
    the acronym, the third the release.
    """
    soup = BeautifulSoup(html, "html.parser")
    work_items: list[WorkItem] = []
    for row in soup.find_all("tr"):
        anchor = row.find("a", href=_WORK_ITEM_UID_LINK)
        if anchor is None:
            continue
        href = str(anchor.get("href") or "")
        uid_match = _WORK_ITEM_UID_LINK.search(href)
        if uid_match is None:
            continue
        cells = _row_cells(row)
        if len(cells) < 2:
            continue
        code = _clean_text(cells[1].get_text())
        if not code or code in {"..."}:
            continue
        level, title = _split_level(anchor.get_text().strip())
        work_items.append(
            WorkItem(
                wi_id=code,
                uid=int(uid_match.group(1)),
                title=title or None,
                release=_clean_text(cells[2].get_text()) if len(cells) > 2 else None,
                level=level,
                lead_body=lead_body.strip().upper(),
            )
        )
    return work_items


def _split_level(title: str) -> tuple[int | None, str]:
    """Split a list title into (level, title) using its known prefix."""
    for prefix, level in _LEVEL_PREFIXES.items():
        if title.lower().startswith(prefix):
            return level, title[len(prefix) :].strip()
    return None, title.strip()


def fetch_work_item_list_entries(
    *,
    timeout: int = 120,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    session: requests.Session | None = None,
) -> list[tuple[int, str, str]]:
    """Fetch and parse the global work item list (uid, code, lead body)."""
    html = _fetch_html(
        work_item_list_url(),
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        session=session,
    )
    return parse_work_item_list_entries(html)


def work_item_list_url() -> str:
    """Return the URL of the global work item list."""
    return DYNAREPORT_URL_TEMPLATE.format(code=WORK_ITEM_LIST_CODE)


def parse_work_item_list_entries(html: str) -> list[tuple[int, str, str]]:
    """Parse the global work item list into (uid, code, lead body) tuples.

    Rows carry five cells: the UID as plain link text, the acronym linking
    to ``WiSpec--<UID>.htm``, the title linking to ``WiCr--<UID>.htm``, the
    release and the lead body linking to ``TSG-WG--<WG>--wis.htm``.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[tuple[int, str, str]] = []
    for row in soup.find_all("tr"):
        cells = _row_cells(row)
        if len(cells) < 5:
            continue
        code = _clean_text(cells[1].get_text())
        if not code or code in {"..."}:
            continue
        wg_anchor = cells[4].find("a", href=_WG_LIST_LINK)
        if wg_anchor is None:
            continue
        wg_match = _WG_LIST_LINK.search(str(wg_anchor.get("href") or ""))
        if wg_match is None:
            continue
        uid = _uid_from_list_row(cells)
        if uid is None:
            continue
        entries.append((uid, code, wg_match.group(1).upper()))
    return entries


def _uid_from_list_row(cells: list[Tag]) -> int | None:
    """Return the UID of a global list row (WiSpec href first, UID cell second)."""
    spec_link = cells[1].find("a", href=re.compile(r"WiSpec--(\d*)\.htm", re.IGNORECASE))
    if spec_link is not None:
        match = re.search(r"WiSpec--(\d+)\.htm", str(spec_link.get("href") or ""), re.IGNORECASE)
        if match is not None:
            return int(match.group(1))
    uid_text = _clean_text(cells[0].get_text())
    if uid_text is not None and uid_text.isdigit():
        return int(uid_text)
    return None


def fetch_work_item_details(
    uid: int,
    *,
    timeout: int = 60,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    session: requests.Session | None = None,
) -> WorkItemDetails:
    """Fetch and parse the portal details page of one work item."""
    html = _fetch_html(
        work_item_details_url(uid),
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        session=session,
    )
    return parse_work_item_details(html, uid=uid)


def work_item_details_url(uid: int) -> str:
    """Return the URL of a work item's portal details page."""
    return WORK_ITEM_DETAILS_URL_TEMPLATE.format(uid=uid)


def parse_work_item_details(html: str, uid: int | None = None) -> WorkItemDetails:
    """Parse a WorkItemDetails.aspx page.

    Raises:
        WorkItemSourceError: If the page carries no work item data.
    """
    soup = BeautifulSoup(html, "html.parser")
    acronym = _label_text(soup, "lblAcronym")
    if acronym is None:
        if "no data available" in html.lower():
            msg = f"Work item details for uid={uid or '?'} returned no data"
            raise WorkItemSourceError(msg)
        msg = "Work item details page has no 'lblAcronym' marker"
        raise WorkItemSourceError(msg)

    resolved_uid = uid
    if resolved_uid is None:
        parent_link = soup.find("a", id="lnkParentWi")
        header = soup.find(string=re.compile(r"WI\s*#\s*(\d+)"))
        match = re.search(r"WI\s*#\s*(\d+)", header or "")
        if match is not None:
            resolved_uid = int(match.group(1))
    if resolved_uid is None:
        msg = "Work item uid could not be determined from the details page"
        raise WorkItemSourceError(msg)

    parent_uid: int | None = None
    parent_title: str | None = None
    parent_link = soup.find("a", id="lnkParentWi")
    if parent_link is not None:
        match = _WORK_ITEM_UID_LINK.search(str(parent_link.get("href", "")))
        if match is not None:
            parent_uid = int(match.group(1))
            parent_title = _clean_text(_label_text(soup, "lblParentWorkItem"))
            if parent_title is not None:
                parent_title = parent_title.lstrip("- ").strip() or None

    child_uids: list[int] = []
    child_grid = soup.find(id="ChildWiTable_GridData")
    if child_grid is not None:
        for anchor in child_grid.find_all("a", href=_WORK_ITEM_UID_LINK):
            match = _WORK_ITEM_UID_LINK.search(str(anchor.get("href") or ""))
            if match is not None:
                child_uids.append(int(match.group(1)))

    return WorkItemDetails(
        uid=resolved_uid,
        wi_id=acronym,
        title=_label_text(soup, "lblName"),
        status=_label_text(soup, "lblStatus"),
        release=_label_text(soup, "lblRelease"),
        level=_details_level(_label_text(soup, "lblWiLevel")),
        parent_uid=parent_uid,
        parent_title=parent_title,
        child_uids=child_uids,
        rapporteur=_label_text(soup, "lblRapporteur"),
    )


def _label_text(soup: BeautifulSoup, element_id: str) -> str | None:
    """Return the text of a labelled details span, e.g. ``lblStatus``."""
    element = soup.find(id=element_id)
    if element is None:
        return None
    return _clean_text(element.get_text())


def _details_level(level_text: str | None) -> int | None:
    """Derive the WI level from the details page label."""
    if level_text is None:
        return None
    ordinal = _ORDINAL_LEVEL.search(level_text)
    if ordinal is not None:
        return int(ordinal.group(1))
    for prefix, level in _LEVEL_PREFIXES.items():
        if level_text.lower().startswith(prefix.rstrip(":")):
            return level
    return None


def fetch_work_item_specs(
    uid: int,
    *,
    timeout: int = 60,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    session: requests.Session | None = None,
) -> list[str]:
    """Fetch and parse the specification list of one work item."""
    html = _fetch_html(
        work_item_specs_url(uid),
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        session=session,
    )
    return parse_work_item_specs(html)


def work_item_specs_url(uid: int) -> str:
    """Return the URL of a work item's specification list."""
    return DYNAREPORT_URL_TEMPLATE.format(code=f"WiSpec--{uid}.htm")


def parse_work_item_specs(html: str) -> list[str]:
    """Parse a WiSpec page into normalized spec numbers."""
    soup = BeautifulSoup(html, "html.parser")
    spec_numbers: list[str] = []
    for anchor in soup.find_all("a", href=_SPEC_HREF):
        text = _clean_text(anchor.get_text())
        if text is None:
            continue
        normalized = normalize_spec_number(text)
        if normalized not in spec_numbers:
            spec_numbers.append(normalized)
    return spec_numbers


def fetch_work_item_crs(
    uid: int,
    *,
    timeout: int = 60,
    http_config: HttpConfig | None = None,
    http_cache_file: Path | None = None,
    session: requests.Session | None = None,
) -> list[WorkItemCr]:
    """Fetch and parse the change request list of one work item."""
    html = _fetch_html(
        work_item_crs_url(uid),
        timeout=timeout,
        http_config=http_config,
        http_cache_file=http_cache_file,
        session=session,
    )
    return parse_work_item_crs(html)


def work_item_crs_url(uid: int) -> str:
    """Return the URL of a work item's change request list."""
    return DYNAREPORT_URL_TEMPLATE.format(code=f"WiCr--{uid}.htm")


def parse_work_item_crs(html: str) -> list[WorkItemCr]:
    """Parse a WiCr page into change requests.

    Rows carry three cells: spec number, CR number and revision
    (``0002`` or ``0002 rev 5``), and the CR title.
    """
    soup = BeautifulSoup(html, "html.parser")
    change_requests: list[WorkItemCr] = []
    for row in soup.find_all("tr"):
        cells = _row_cells(row)
        if len(cells) < 2:
            continue
        spec_text = _clean_text(cells[0].get_text())
        cr_text = _clean_text(cells[1].get_text())
        if spec_text is None or cr_text is None:
            continue
        parts = cr_text.split()
        cr_number = parts[0]
        revision = parts[2] if len(parts) >= 3 and parts[1].lower() == "rev" else None
        cr_title = _clean_text(cells[2].get_text()) if len(cells) > 2 else None
        change_requests.append(
            WorkItemCr(
                spec_number=spec_text,
                cr_number=cr_number,
                cr_revision=revision,
                cr_title=cr_title,
            )
        )
    return change_requests


def _clean_text(value: str | None) -> str | None:
    """Collapse whitespace and drop placeholder values."""
    if value is None:
        return None
    text = " ".join(value.split()).replace("‑", "-").replace("–", "-")
    if text.lower() in _PLACEHOLDER_TEXTS:
        return None
    return text or None


def _row_cells(row: Tag) -> list[Tag]:
    """Return the <td> cells of a table row."""
    return list(row.find_all("td", recursive=False))


# ---------------------------------------------------------------------------
# Fetching


def _fetch_html(
    url: str,
    *,
    timeout: int,
    http_config: HttpConfig | None,
    http_cache_file: Path | None,
    session: requests.Session | None,
) -> str:
    """GET a work item page as text using the given or a fresh session."""
    own_session = session is None
    active = session if session is not None else create_cached_session(http_config=http_config, http_cache_file=http_cache_file)
    try:
        response = active.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text or ""
    except requests.RequestException as exc:
        msg = f"Failed to fetch {url}: {exc}"
        raise WorkItemSourceError(msg) from exc
    finally:
        if own_session:
            active.close()


__all__ = [
    "WORK_ITEM_LIST_CODE",
    "WorkItemSourceError",
    "discover_lead_bodies",
    "fetch_wg_work_items",
    "fetch_work_item_crs",
    "fetch_work_item_details",
    "fetch_work_item_list_entries",
    "fetch_work_item_specs",
    "fetch_work_items",
    "parse_lead_bodies",
    "parse_wg_work_items",
    "parse_work_item_crs",
    "parse_work_item_details",
    "parse_work_item_list_entries",
    "parse_work_item_specs",
    "wg_work_items_url",
    "work_item_crs_url",
    "work_item_details_url",
    "work_item_list_url",
    "work_item_session",
    "work_item_specs_url",
]
