# MCP Server

`3gpp-crawler mcp` starts a stdio [Model Context Protocol](https://modelcontextprotocol.io)
server (fastmcp) that exposes the crawler to AI agents.

## Starting

```bash
3gpp-crawler mcp
```

## Tools

Tools mirror the CLI groups:

| Group | Tool | CLI equivalent |
|-------|------|----------------|
| crawl | `crawl_tdocs` | `tdoc crawl` |
| crawl | `crawl_specs` | `spec crawl` |
| crawl | `crawl_meetings` | `meetings crawl` |
| crawl | `crawl_work_items` | `work-items crawl` |
| enrich | `enrich_work_items` | `work-items enrich` |
| query | `query_tdocs` | `tdoc query` |
| query | `query_work_items` | `work-items query` |
| query | `query_specs` | `spec query` |
| query | `query_meetings` | `meetings query` |
| checkout | `checkout_tdocs` | `tdoc checkout` |
| checkout | `checkout_specs` | `spec checkout` |
| checkout | `list_tdoc_files` | `tdoc files` |
| checkout | `list_spec_files` | `spec files` |
| main-file | `get_tdoc_main_file` | `tdoc open` (resolve only) |
| main-file | `main_file_set` | `tdoc main-file set` |
| main-file | `main_file_show` | `tdoc main-file show` |
| main-file | `main_file_list` | `tdoc main-file list` |
| main-file | `main_file_clear` | `tdoc main-file clear` |
| main-file | `reclassify_main_files` | `tdoc main-file reclassify` |
| tag | `tag_add` | `tag add` |
| tag | `tag_remove` | `tag remove` |
| tag | `tag_list` | `tag list` |
| database | `database_clear_tdocs` | `database clear-tdocs` |
| database | `database_clear_specs` | `database clear-specs` |
| database | `database_clear_meetings` | `database clear-meetings` |
| database | `database_clear_all` | `database clear-all` |
| database | `database_export_tags` | `database export-tags` |
| database | `database_import_tags` | `database import-tags` |
| config | `config_show` | `config show` |

The `database_clear_*` tools delete records only. Downloaded TDoc and Spec
files stay in the checkout directory unless `purge_checkouts=true` is passed;
that is irreversible and rarely needed, because TDocs never change.
| config | `config_validate` | `config validate` |

Notable parameters: `query_tdocs` accepts a `tag` list (comma = OR,
repeated = AND, same as the CLI). `crawl_tdocs`, `crawl_meetings`,
`query_tdocs` and `query_meetings` accept `subgroup` (e.g. `["SA4"]`, `["S4"]`,
`["R1"]`) alongside `working_group`. Working groups are only RAN/SA/CT — passing
a subgroup code as `working_group` is rejected rather than silently
collapsing to the plenary (`SA4` → `SA`). `crawl_tdocs` accepts `meeting`
(repeatable patterns: `["SA4#138"]`, `["S4-138"]`, `["SA4#13*"]`, or meeting
IDs), mirroring `tdoc crawl --meeting`.

`query_tdocs` also accepts `work_item` (e.g. `["ULBC-MED"]`) to select every
TDoc whose meeting document list row references that 3GPP work item, and
`spec_number` (e.g. `["26.114"]`) to select TDocs that name that specification.
`crawl_work_items` crawls the per-lead-body DynaReport work item lists; scope
it with `subgroup` (e.g. `["S4"]`, also historical lead bodies like `"GP"`) or
`working_group` (an area: `RAN`/`SA`/`CT`), or omit both to discover every
lead body. `enrich_work_items` fills status, parent/child and spec/CR links
from the portal detail pages (default: TDoc-referenced and never-enriched work
items; pass `work_item`/`limit`/`include_all` to steer). `query_work_items`
reads the resulting catalogue: titles, releases, approval status, lead body,
parent work item and impacted specifications, plus the number of TDocs
referencing each work item (from the `Related WIs` column during
`crawl_tdocs`). A database crawled before work item support holds none —
rebuild it with `database_clear_all` and re-crawl.

The destructive `database_clear_*` tools refuse to run unless called with
`confirm=true` — there is no interactive prompt over MCP, so the explicit
flag is the confirmation (and costs agents one deliberate extra round-trip).
Prefer `database_export_tags` first when a backup would help.

Main-document selection is available over MCP. `get_tdoc_main_file`
downloads, extracts and resolves the main document but does **not** launch
it — it returns the absolute path, the archive-relative member, and the
source (`manual_override`, `decision_model`, `heuristic`). The
`main_file_*` tools manage overrides, and `reclassify_main_files` replays
classification for checked-out TDocs (`tdoc_ids` or `all_tdocs=true`);
manual choices are protected unless `include_manual=true`, which deletes
those overrides first. `selector` may be overridden per call. Selection
settings live in the `[checkout]` section — configure them once in the
global `~/.config/3gpp-crawler/config.toml` so MCP and the CLI share them.

## Client configuration

Add to any MCP-capable agent client:

```json
{
  "mcpServers": {
    "3gpp-crawler": {
      "command": "3gpp-crawler",
      "args": ["mcp"]
    }
  }
}
```

When running from a checkout instead of an installed tool:

```json
{
  "mcpServers": {
    "3gpp-crawler": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/3gpp-crawler", "3gpp-crawler", "mcp"]
    }
  }
}
```

## Output format

Tools currently return captured console text — fine for LLM consumption.
For machine-parseable output, run the CLI directly with `--output json`.
