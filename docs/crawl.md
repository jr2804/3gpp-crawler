# Crawling Metadata

Crawling gathers metadata from external sources (3GPP FTP server, 3GPP
Portal, [WhatTheSpec](whatthespec.md)) and stores it in your local SQLite
database.

## Prerequisites

**Meetings must be crawled first**: the TDoc crawl relies on the meetings
database to know which meeting directories to visit on the FTP server.

## Commands

### `crawl-meetings` (alias: `cm`)

Crawl meeting metadata from the 3GPP portal.

```bash
3gpp-crawler tdoc crawl-meetings              # all working groups
3gpp-crawler tdoc crawl-meetings -s S4        # SA4 subgroup only
3gpp-crawler tdoc crawl-meetings --limit-meetings-per-wg 10
```

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Working groups to crawl (repeatable): `RAN`, `SA`, `CT`. |
| `-s, --sub-group SG` | Sub-working groups to crawl (repeatable), e.g. `S4`, `R1`. |
| `--incremental / --full` | Incremental skips existing meetings; `--full` reprocesses. |
| `--limit-meetings-per-wg N` | Maximum meetings per working group. |
| `--eol-username USER` | ETSI Online account (faster authenticated access). |

### `crawl` (alias: `ct`)

Crawl TDoc metadata from the 3GPP FTP server.

```bash
3gpp-crawler tdoc crawl                       # all TDocs (after crawl-meetings)
3gpp-crawler tdoc crawl -w RAN -s R1 -s R2    # specific subgroups
3gpp-crawler tdoc crawl --start-date 2024     # date-filtered
3gpp-crawler tdoc crawl --workers 8           # parallel workers
```

| Option | Description |
|--------|-------------|
| `-w, --working-group WG` | Working groups to crawl (repeatable). |
| `-s, --sub-group SG` | Sub-working groups to crawl (repeatable). |
| `--incremental / --full` | Incremental skips existing TDocs. |
| `--workers N` | Parallel workers (default: 4). |
| `--checkout` | Download and extract crawled TDocs to the checkout folder. |
| `--start-date / --end-date` | ISO 8601 date filters. |
| `--source / --title / --agenda` | Glob patterns; `-ex` variants exclude. |
| `--limit-tdocs N` | Limit TDocs per crawl. |

### `crawl` (specs)

Crawl technical specification (TS/TR) metadata.

```bash
3gpp-crawler spec crawl                       # all specs from all sources
3gpp-crawler spec crawl 26260                 # specific spec
3gpp-crawler spec crawl -w SA4                # filter by working group
```

| Option | Description |
|--------|-------------|
| `SPEC_NUMBERS` | Positional spec numbers (dotted or undotted). |
| `-w, --working-group WG` | Working groups to crawl. |

Sources (`3gpp`, `whatthespec`) are configured in your
[configuration](config.md); by default both are used.

## Shortcuts

The `tdoc-crawler` and `spec-crawler` entry points run the same commands
without the group prefix:

```bash
tdoc-crawler crawl --start-date 2024
spec-crawler crawl 26260
```
