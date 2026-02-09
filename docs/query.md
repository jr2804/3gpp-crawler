# Querying Metadata

Query commands allow you to search and display metadata stored in your local database. They support various output formats like tables, JSON, and YAML.

## Commands

### `query-tdocs` (alias: `qt`)

Search for TDocs by ID, working group, or date range.

**Targeted Fetching:**
If you query a TDoc ID that is not in your database, `tdoc-crawler` automatically attempts to find it on the portal and FTP server. This makes the tool very resilient even if you haven't run a full crawl.

**Options:**

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Filter by working group (repeatable). |
| `-o, --output FORMAT` | `table`, `json`, `yaml` (default: `table`). |
| `-l, --limit N` | Maximum number of results. |
| `--start-date TIMESTAMP` | Filter from ISO 8601 date. |
| `--no-fetch` | Disable automatic fetching of missing TDocs. |

**Examples:**

```bash
# Query specific TDoc (auto-fetches if missing)
tdoc-crawler query-tdocs R1-2400001

# Filter by working group and limit
tdoc-crawler query-tdocs --working-group RAN --limit 20

# Export results as JSON
tdoc-crawler query-tdocs R1-2400001 --output json
```

---

### `query-meetings` (alias: `qm`)

Browse meeting schedules and metadata. Unlike `query-tdocs`, this command only searches already-crawled meetings.

**Options:**

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Filter by working group (`RAN`, `SA`, `CT`, `RP`, `SP`, `CP`). |
| `-s, --sub-group SG` | Filter by sub-working group (e.g., `S4`, `R1`). |
| `-o, --output FORMAT` | `table`, `json`, `yaml`. |
| `--include-without-files` | Include meetings without FTP file links. |

**Examples:**

```bash
# List SA meetings
tdoc-crawler query-meetings -w SA

# Filter RAN Plenary
tdoc-crawler query-meetings -w RP -s "RAN Plenary"

# Export as YAML
tdoc-crawler query-meetings --output yaml
```

---

### `query-specs` (alias: `qs`)

Query technical specification metadata from the local catalog.

**Options:**

| Option | Description |
|--------|-------------|
| `-w, --group WG` | Filter by working group. |
| `-s, --status STATUS` | Filter by status (e.g., "Under change control"). |
| `-v, --verbose` | Show per-source discrepancy details. |

**Examples:**

```bash
# Query specific spec
tdoc-crawler query-specs 23.501

# Filter by status
tdoc-crawler query-specs --status "Under change control"
```
