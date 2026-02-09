# Crawling Metadata

Crawling is the process of gathering metadata from external sources (3GPP FTP server, 3GPP Portal, WhatTheSpec) and storing it in your local SQLite database.

## Prerequisites

- **Meetings must be crawled first**: The `crawl-tdocs` command relies on the meetings database to know which meeting directories to visit on the FTP server.

## Commands

### `crawl-meetings` (alias: `cm`)

Crawl meeting metadata from the 3GPP portal.

**When to Use:**

- Initial setup (required before first TDoc crawl).
- Periodic updates to meeting schedules.
- Adding new working groups to crawl.

**Options:**

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Working groups to crawl (repeatable). `RAN`, `SA`, `CT`. |
| `-s, --sub-group SG` | Sub-working groups to crawl (repeatable). |
| `--incremental/--full` | Incremental mode skips existing; `--full` forces reprocessing. |
| `--limit-meetings-per-wg N` | Maximum meetings per working group. |
| `--eol-username USER` | ETSI Online account username (faster authenticated access). |

**Examples:**

```bash
# Initial setup
tdoc-crawler crawl-meetings

# Specific working group
tdoc-crawler crawl-meetings -w SA

# Recent meetings only
tdoc-crawler crawl-meetings --limit-meetings-per-wg 10
```

______________________________________________________________________

### `crawl-tdocs` (alias: `ct`)

Crawl TDoc metadata from the 3GPP FTP server.

**When to Use:**

- Initial TDoc metadata population.
- Incremental updates to your local TDoc database.
- After running `crawl-meetings` to refresh TDoc data.

**Options:**

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Working groups to crawl. |
| `-s, --sub-group SG` | Sub-working groups to crawl. |
| `--incremental/--full` | Incremental mode skips existing TDocs. |
| `--workers N` | Number of parallel workers (default: 4). |
| `--checkout` | Download and extract crawled TDocs to checkout folder. |

**Examples:**

```bash
# Crawl all TDocs (after crawl-meetings)
tdoc-crawler crawl-tdocs

# Specific subgroup
tdoc-crawler crawl-tdocs -w RAN -s R1 -s R2

# Faster crawl with more workers
tdoc-crawler crawl-tdocs -w RAN --workers 8
```

______________________________________________________________________

### `crawl-specs` (alias: `cs`)

Crawl technical specification (TS/TR) metadata.

**When to Use:**

- Populating the specs catalog for searching/viewing specs.
- Synchronizing latest spec versions and titles.

**Options:**

| Option | Description |
|--------|-------------|
| `-s, --source SOURCE` | Metadata sources: `3gpp`, `whatthespec`. Default: both. |
| `-w, --working-group WG` | Working groups to crawl. |

**Examples:**

```bash
# Crawl all specs from all sources
tdoc-crawler crawl-specs

# Crawl only RAN specs from whatthespec
tdoc-crawler crawl-specs -w RAN -s whatthespec
```
