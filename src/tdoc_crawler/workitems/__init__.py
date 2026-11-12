"""3GPP work item catalogue: models, sources and operations."""

from __future__ import annotations

from tdoc_crawler.workitems.models import WorkItem, WorkItemCr, WorkItemDetails
from tdoc_crawler.workitems.sources.dynareport import (
    WorkItemSourceError,
    discover_lead_bodies,
    fetch_wg_work_items,
    fetch_work_item_crs,
    fetch_work_item_details,
    fetch_work_item_list_entries,
    fetch_work_item_specs,
    fetch_work_items,
    parse_lead_bodies,
    parse_wg_work_items,
    parse_work_item_crs,
    parse_work_item_details,
    parse_work_item_list_entries,
    parse_work_item_specs,
    wg_work_items_url,
    work_item_details_url,
)

__all__ = [
    "WorkItem",
    "WorkItemCr",
    "WorkItemDetails",
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
    "work_item_details_url",
]
