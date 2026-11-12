# Querying Metadata

Query commands search metadata stored in your local database and display
it as tables, JSON, or YAML.

## Commands

### `query` (TDocs, alias: `qt`)

Search TDocs by ID, working group, date range, title, agenda, work item, or
[tags](tags.md).

**Work items** come from two sources: the `Related WIs` column of the meeting
document lists (a comma-separated list of WI IDs such as `FS_ULBC, ULBC-MED`)
links a TDoc to a work item, and the DynaReport work item lists
(`3gpp-crawler work-items crawl`) supply titles, releases, approvals, the
parent work item and impacted specifications; `work-items enrich` adds
parent/child and spec/CR details from the portal pages. The `Related WIs`
column exists only in recent document lists, so work-item filters only match
TDocs crawled after the work item support was added.

**Agenda hierarchy**: a document list only names the leaf agenda item a
document was filed under. The parent items (for example `4 ULBC-MED` above
`4.5 Qualification/Selection rules`) are taken from the meeting's own agenda
document while crawling, so `--agenda ULBC-MED` also finds the documents
filed under its children. Parents exist only for meetings crawled after the
agenda document was parsed — older databases need
`3gpp-crawler database clear-all` followed by a re-crawl.

**Targeted fetching**: if you query a TDoc ID that is not in your database,
the tool automatically attempts to fetch it from the portal and FTP server.
Disable with `--no-fetch`.

```bash
3gpp-crawler tdoc query R1-260001             # specific ID (auto-fetches)
3gpp-crawler tdoc query --working-group SA --limit 20
3gpp-crawler tdoc query --agenda "*codec*" --start-date 2024
3gpp-crawler tdoc query --tag codec,rel-18    # tag filter (OR within option)
3gpp-crawler tdoc query --tag codec --tag rel-18   # tag filter (AND across)
3gpp-crawler tdoc query --output json         # JSON output
```

| Option | Description |
|--------|-------------|
| `TDOC_IDS` | Positional TDoc identifiers. |
| `-w, --working-group WG` | Filter by working group (`RAN`, `SA`, `CT`). A sub-working-group code such as `SA4` is rejected here. |
| `-s, --sub-group SG` | Filter by sub-working group (e.g. `S4`, `R1`). |
| `-i, --work-item WI` | Filter by 3GPP work item ID (e.g. `ULBC-MED`). |
| `--spec-number SPEC` | Filter by the specification named in the document list row (e.g. `26.114`). |
| `--start-date / --end-date` | ISO 8601 timestamp filters. |
| `--source / --title / --agenda` | Glob patterns; bare patterns (no `*?[]`) substring-match. `-ex` variants exclude. `--agenda` also matches parent agenda items. |
| `-t, --tag TAGS` | Tag filter (repeatable, comma = OR). See [Tags](tags.md). |
| `-l, --limit N` | Maximum rows. |
| `--order` | `asc` or `desc`. |
| `--sort-by KEY` | Sort key: `meeting_date` (default), `reservation_date`, `uploaded_at`, `tdoc_id`. |
| `-o, --output FORMAT` | `table`, `json`, `yaml`. |
| `--fetch / --no-fetch` | Automatic fetching of missing TDocs (default: on). |
| `--checkout` | Download and extract the matched TDocs. |

The JSON/YAML output and table both include the true source timestamps
`reservation_date` (3GPP reservation slot) and `uploaded_at` (actual upload/
revision time). These are captured from the meeting document list; use
`--sort-by uploaded_at` to order by real submission time rather than TDoc
number (which reflects reservation order, not upload order).

```bash
3gpp-crawler tdoc query --sub-group S4 --sort-by uploaded_at --order desc --limit 20
3gpp-crawler tdoc query --work-item ULBC-MED   # every TDoc of a work item
```

### `work-items query` (top level, not under `tdoc`)

Query the work item catalogue built from the DynaReport work item lists. Work
items carry their title, release, approval status, lead body, parent work
item, impacted specifications and — when TDocs have been crawled — the number
of TDocs that reference them.

```bash
3gpp-crawler work-items crawl                  # all lead bodies (discovered)
3gpp-crawler work-items crawl -s S4            # one lead body
3gpp-crawler work-items enrich                 # fill status/parents/specs/CRs
3gpp-crawler work-items query                  # all work items
3gpp-crawler work-items query ULBC-MED --show-specs
3gpp-crawler work-items query -w SA -r Rel-20
3gpp-crawler work-items query --status stopped --output json
```

| Option | Description |
|--------|-------------|
| `WORK_ITEM_IDS` | Positional work item IDs (e.g. `ULBC-MED FS_ULBC`). |
| `-w, --working-group WG` | Only work items referenced by TDocs of that working group (`RAN`, `SA`, `CT`). |
| `-r, --release REL` | Filter by release (e.g. `Rel-20`). |
| `--status STATUS` | Filter by status (`PCG approved`, `TSG approved`, `stopped`). |
| `--show-specs / --no-show-specs` | Show the impacted specifications per work item. |
| `-l, --limit N` | Maximum rows. |
| `-o, --output FORMAT` | `table`, `json`, `yaml`. |

The `Lead` column names the responsible group (`S4`, `R1`, …) each work item
was crawled from. `work-items enrich` walks the 3GPP portal detail pages for
the selected work items (by default the TDoc-referenced and never-enriched
ones) and fills status, release, level, parent/child and the specification /
change-request links; `work-items audit` compares the local catalogue against
the global `WI-List` page and reports per-lead-body coverage.

### `query-meetings` (alias: `qm`)

Browse crawled meeting schedules and metadata.

```bash
3gpp-crawler tdoc query-meetings -w SA
3gpp-crawler tdoc query-meetings -s S4
3gpp-crawler tdoc query-meetings --output yaml
```

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Filter by working group (`RAN`, `SA`, `CT`). |
| `-s, --sub-group SG` | Filter by sub-working group (e.g. `S4`, `R1`). |
| `-o, --output FORMAT` | `table`, `json`, `yaml`. |

### `query` (specs)

Query technical specification metadata from the local catalog.

```bash
3gpp-crawler spec query 23.501
3gpp-crawler spec query --status "Under change control"
3gpp-crawler spec query --working-group SA4     # or -w S4, -w RAN1
3gpp-crawler spec query --tag rel-18
```

| Option | Description |
|--------|-------------|
| `SPEC_NUMBERS` | Positional spec numbers (dotted or undotted). |
| `--status STATUS` | Filter by status. |
| `-w, --working-group WG` | Filter by working group or sub-working group (`SA4`/`S4`, `RAN1`/`R1`, or plain `SA`/`RAN`/`CT`). |
| `-t, --tag TAGS` | Tag filter (repeatable, comma = OR). See [Tags](tags.md). |
| `-o, --output FORMAT` | `table`, `json`, `yaml`. |

## Shortcuts

`tdoc-crawler query …` and `spec-crawler query …` run the same commands
without the group prefix.
