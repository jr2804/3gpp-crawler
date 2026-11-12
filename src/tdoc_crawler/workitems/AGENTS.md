# Work Items Submodule

Work item catalogue: the DynaReport work item lists, the portal detail pages,
and the domain model shared by `database/` and `cli/`.

## Purpose

Turn the public 3GPP DynaReport work item lists into `WorkItem` records for
the local `workitemrecord` / `workitemspecrecord` tables, enrich them from the
portal detail pages, and answer "which work items exist, what do they touch,
and under which parent do they hang".

## Ownership

- `models.py` — pydantic models: `WorkItem` (`wi_id`, `uid`, `title`,
  `release`, `status`, `level`, `parent_wi_id`, `parent_uid`, `lead_body`,
  `spec_numbers`; validators upper-case the ID and normalise spec numbers),
  `WorkItemDetails` (portal detail page), `WorkItemCr` (WiCr rows; `cr_number`
  zero-fills to 4 digits).
- `sources/dynareport.py` — URL builders, HTML parsers and fetchers for the
  DynaReport pages and `WorkItemDetails.aspx`; `WorkItemSourceError` is the
  single error type (parsing and network).
- `operations.py` — lead-body code normalisation (`normalize_wg_codes`,
  `expand_area_codes`), `enrich_work_items`, `compare_work_item_list`.

Database persistence and CLI/MCP surfaces are owned by `database/AGENTS.md`
and `cli/AGENTS.md`; this package must not import either.

## Local Contracts

- Pages (all public, no login): `dynareport?code=WI-List` (global list, lags
  for in-flight WIs — discovery + audit only), `dynareport?code=TSG-WG--<WG>--wis.htm`
  (per lead body, current — the crawl source), `WiSpec--<UID>.htm` /
  `WiCr--<UID>.htm` (outputs per WI, empty when nothing published yet) and
  `WorkItemDetails.aspx?workitemId=<UID>` (numeric UID required).
- Per-WG rows: title cell links to `WorkItemDetails.aspx?workitemId=<UID>`
  (hrefs are unquoted), code cell is the WI ID, release cell like `Rel-20`.
  Title prefixes map to `level`: "Feature or Study Item" → 1, "Building
  Block" → 2, "Work task" → 3.
- `WI-List` rows have five cells (UID anchor, code with `WiSpec--<UID>.htm`
  link, title, release with non-breaking hyphens, lead body with
  `TSG-WG--<WG>--wis.htm` link); junk rows use `...` as code and are skipped.
- Lead bodies include historical groups not in `SubWorkingGroup` (`G1`,
  `N2`, `T3`, `SMG`, `GP`, …); `normalize_wg_codes` passes them through
  uppercased.
- Fetchers accept `session=` so enrichment walks many WIs on one session.
- Do not scrape `Specifications.aspx`/`ChangeRequests.aspx` grids or
  `WorkItems.aspx` — they render through Telerik postbacks and need a login.
  The FTP work plan spreadsheet (`Work_plan_*.xlsx`) was removed on purpose:
  its handcrafted filename is unstable; do not reintroduce it.

## Work Guidance

- Extend the parsers in `sources/dynareport.py` rather than parsing the HTML
  elsewhere; keep parsers pure (HTML in, models out) and tested with inline
  fixtures.
- TDoc↔work-item links come from the document list `Related WIs` column (see
  `tdocs/sources/doclist.py`), never from these pages.

## Verification

`uv run pytest tests/test_dynareport.py tests/test_workitems_operations.py -q`
