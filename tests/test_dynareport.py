"""Tests for the DynaReport work item source pages."""

from __future__ import annotations

import pytest

from tdoc_crawler.workitems import (
    WorkItemSourceError,
    parse_lead_bodies,
    parse_wg_work_items,
    parse_work_item_crs,
    parse_work_item_details,
    parse_work_item_list_entries,
    parse_work_item_specs,
    wg_work_items_url,
    work_item_details_url,
)

_WG_PAGE = """
<html><body><table>
<tr><th>Title</th><th>Code</th><th>Release</th></tr>
<tr class="even">
  <td width="800"><a href=https://portal.3gpp.org/desktopmodules/WorkItem/WorkItemDetails.aspx?workitemId=1120096>Building Block: ULB Codec</a></td>
  <td width="150">ULBC-MED</td>
  <td width="50">Rel-20</td>
</tr>
<tr class="odd">
  <td width="800"><a href="https://portal.3gpp.org/desktopmodules/WorkItem/WorkItemDetails.aspx?workitemId=1120095">Feature or Study Item: ULBC study</a></td>
  <td width="150">FS_ULBC</td>
  <td width="50">Rel-20</td>
</tr>
<tr class="even">
  <td width="800"><a href="https://portal.3gpp.org/desktopmodules/WorkItem/WorkItemDetails.aspx?workitemId=1120060">Work task: CT aspects</a></td>
  <td width="150">ULBC-MED-CT</td>
  <td width="50">Rel-20</td>
</tr>
<tr class="odd"><td colspan="3">No links in this row</td></tr>
</table></body></html>
"""

_GLOBAL_LIST = """
<html><body><table>
<tr bgcolor="#BEF781"><th><b>UID</b></th><th><b>code</b></th><th><b>title</b></th><th><b>Release</b></th><th><b>lead_body</b></th></tr>
<tr class="even">
  <td><p align="right"><a name="bm0" href="/DynaReport/GanttChart-Level-2.htm#bm0">970284</a></p></td>
  <td><a target="_blank" href="/DynaReport/WiSpec--970284.htm">FS_ULBC</a></td>
  <td><a target="_blank" href="/DynaReport/WiCr--970284.htm">Study on Ultra Low Bitrate Speech Codec</a></td>
  <td>Rel&#8209;19</td>
  <td><a href="/DynaReport/TSG-WG--S4--wis.htm">S4</a></td>
</tr>
<tr class="odd">
  <td><p align="right"><a name="bm1" href="/DynaReport/GanttChart-Level-2.htm#bm1">1080054</a></p></td>
  <td><a target="_blank" href="/DynaReport/WiSpec--1080054.htm">5GSAT_PH4</a></td>
  <td><a target="_blank" href="/DynaReport/WiCr--1080054.htm">Satellite access - Phase 4</a></td>
  <td>Rel&#8209;20</td>
  <td><a href="/DynaReport/TSG-WG--SP--wis.htm">SP</a></td>
</tr>
</table></body></html>
"""

_SPEC_PAGE = """
<html><body><table class="dsptab adynspec tablesorter wispec">
<tr><td><a href="/DynaReport/26071.htm">26.071</a></td></tr>
<tr><td><a href="/DynaReport/26071.htm">26.071</a></td></tr>
<tr><td><a href="/DynaReport/26501.htm">26.501</a></td></tr>
</table></body></html>
"""

_CR_PAGE = """
<html><body><table>
<tr><th>Spec</th><th>CR</th><th>Title</th></tr>
<tr><td><a href="/DynaReport/26071.htm">26.071</a></td><td><a href="26071-CRs.htm#0002rev-">0002 rev 5</a></td><td>ULBC support</td></tr>
<tr><td><a href="/DynaReport/26071.htm">26.071</a></td><td><a href="26071-CRs.htm#0003rev-">0003</a></td><td>Another correction</td></tr>
</table></body></html>
"""

_DETAILS_PAGE = """
<html><body>
<span id="lblName">Ultra Low Bitrate Speech Codec</span>
<span id="lblAcronym">ULBC-MED</span>
<span id="lblWiLevel">Building Block (2nd level)</span>
<span id="lblStatus">PCG approved</span>
<span id="lblRelease">Rel-20</span>
<span id="lblStartDate">2026-06-04</span>
<span id="lblEndDate">2027-06-06</span>
<a id="lnkParentWi" href="WorkItemDetails.aspx?workitemId=1080054">1080054</a>
<span id="lblParentWorkItem"> - Satellite access - Phase 4</span>
<span id="lblRapporteur">suhuanyu@vivo.com (Huan-Yu Su, vivo)</span>
<div id="ChildWiTable_GridData">
  <table><tr><td><a href="WorkItemDetails.aspx?workitemId=1120060">ULBC-MED-CT</a></td></tr></table>
</div>
</body></html>
"""


class TestParseWgWorkItems:
    def test_parses_rows_with_level_prefixes(self) -> None:
        items = parse_wg_work_items(_WG_PAGE, lead_body="s4")

        assert [item.wi_id for item in items] == ["ULBC-MED", "FS_ULBC", "ULBC-MED-CT"]
        ulbc = items[0]
        assert ulbc.uid == 1120096
        assert ulbc.title == "ULB Codec"
        assert ulbc.level == 2
        assert ulbc.release == "Rel-20"
        assert ulbc.lead_body == "S4"
        assert items[1].level == 1
        assert items[2].level == 3

    def test_skips_rows_without_work_item_links(self) -> None:
        items = parse_wg_work_items("<table><tr><td>x</td><td>y</td></tr></table>", lead_body="S4")

        assert items == []


class TestParseWorkItemListEntries:
    def test_extracts_uid_code_and_lead_body(self) -> None:
        entries = parse_work_item_list_entries(_GLOBAL_LIST)

        assert entries == [(970284, "FS_ULBC", "S4"), (1080054, "5GSAT_PH4", "SP")]

    def test_discovers_lead_bodies(self) -> None:
        lead_bodies = parse_lead_bodies(_GLOBAL_LIST)

        assert lead_bodies == ["S4", "SP"]


class TestParseWorkItemSpecs:
    def test_collects_unique_spec_numbers(self) -> None:
        specs = parse_work_item_specs(_SPEC_PAGE)

        assert specs == ["26.071", "26.501"]

    def test_empty_page_has_no_specs(self) -> None:
        assert parse_work_item_specs("<html><body>No table</body></html>") == []


class TestParseWorkItemCrs:
    def test_parses_revision_and_title(self) -> None:
        crs = parse_work_item_crs(_CR_PAGE)

        assert [(cr.spec_number, cr.cr_number, cr.cr_revision) for cr in crs] == [
            ("26.071", "0002", "5"),
            ("26.071", "0003", None),
        ]
        assert crs[0].cr_title == "ULBC support"


class TestParseWorkItemDetails:
    def test_parses_labels_parent_and_children(self) -> None:
        details = parse_work_item_details(_DETAILS_PAGE, uid=1120096)

        assert details.uid == 1120096
        assert details.wi_id == "ULBC-MED"
        assert details.title == "Ultra Low Bitrate Speech Codec"
        assert details.status == "PCG approved"
        assert details.release == "Rel-20"
        assert details.level == 2
        assert details.parent_uid == 1080054
        assert details.parent_title == "Satellite access - Phase 4"
        assert details.child_uids == [1120060]

    def test_no_data_page_raises(self) -> None:
        with pytest.raises(WorkItemSourceError, match="no data"):
            parse_work_item_details("<html><body>No data available for the current query.</body></html>", uid=1)

    def test_page_without_marker_raises(self) -> None:
        with pytest.raises(WorkItemSourceError, match="lblAcronym"):
            parse_work_item_details("<html><body>empty</body></html>", uid=1)


class TestUrlBuilders:
    def test_urls_use_dynareport_templates(self) -> None:
        assert wg_work_items_url("s4") == "https://www.3gpp.org/dynareport?code=TSG-WG--S4--wis.htm"
        assert work_item_details_url(1120096) == "https://portal.3gpp.org/desktopmodules/WorkItem/WorkItemDetails.aspx?workitemId=1120096"
