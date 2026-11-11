# Querying Metadata

Query commands search metadata stored in your local database and display
it as tables, JSON, or YAML.

## Commands

### `query` (TDocs, alias: `qt`)

Search TDocs by ID, working group, date range, title, agenda, or
[tags](tags.md).

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
| `--start-date / --end-date` | ISO 8601 timestamp filters. |
| `--source / --title / --agenda` | Glob patterns; bare patterns (no `*?[]`) substring-match. `-ex` variants exclude. |
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
```

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
