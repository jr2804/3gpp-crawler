# TDoc Crawler – Quick Reference

Single source of truth for the CLI behaviour. All examples assume execution from the project root.

## Command Overview

TDoc-Crawler provides two categories of commands: **Crawling Commands** for gathering data, and **Query Commands** for retrieving stored information.

### Command Categories

| Category | Commands | Purpose |
|----------|----------|---------|
| **Crawling** | `crawl-tdocs`, `crawl-meetings` | Fetch metadata from 3GPP servers and portal |
| **Querying** | `query-tdocs`, `query-meetings` | Search and display stored metadata |
| **Utilities** | `open`, `checkout`, `stats` | File access and database inspection |

### Short Aliases

| Command | Alias |
|---------|-------|
| `crawl-tdocs` | `ct` |
| `crawl-meetings` | `cm` |
| `query-tdocs` | `qt` |
| `query-meetings` | `qm` |

Use aliases for faster typing: `tdoc-crawler ct` instead of `tdoc-crawler crawl-tdocs`.

## Shared Behaviour

- Cache files and the SQLite database default to `~/.tdoc-crawler`; override with `--cache-dir`.
- Incremental crawls skip IDs already stored; pass `--full` to force reprocessing.
- Queries that specify `tdoc_ids` automatically launch a targeted crawl when a requested ID is missing; results refresh before output.
- Targeted crawls infer working groups from the prefix of each TDoc ID (`R`, `S`, `T`, `C`).
- Downloaded TDocs live under `<cache-dir>/tdocs/` and are reused when possible.

## Typical Workflow

The typical workflow for using TDoc-Crawler involves three phases:

### 1. Initial Setup (One-time)

```bash
# Step 1: Crawl meeting metadata first (required before crawling TDocs)
tdoc-crawler crawl-meetings

# Step 2: Crawl TDoc metadata
tdoc-crawler crawl-tdocs
```

### 2. Incremental Updates (Regular)

```bash
# Update meetings (faster - only checks for new meetings)
tdoc-crawler crawl-meetings

# Update TDocs (only fetches new/updated TDocs)
tdoc-crawler crawl-tdocs
```

### 3. Querying (On-demand)

```bash
# Query specific TDocs by ID
tdoc-crawler query-tdocs R1-2400001 S2-2400567

# Query all TDocs from a working group
tdoc-crawler query-tdocs --working-group RAN

# Query meetings
tdoc-crawler query-meetings
```

## Command Differences

### Crawl Commands: `crawl-tdocs` vs `crawl-meetings`

| Aspect | `crawl-tdocs` | `crawl-meetings` |
|--------|---------------|------------------|
| **Data Source** | 3GPP FTP server | 3GPP Portal (web scraping) |
| **Data Type** | TDoc metadata and file links | Meeting schedules, attendees, locations |
| **Prerequisites** | Meetings database must exist | No prerequisites |
| **Execution Order** | Run AFTER `crawl-meetings` | Run FIRST |
| **Credentials** | Not required (FTP is public) | Optional (EOL account for faster access) |
| **Typical Duration** | Minutes to hours (large data volume) | Seconds to minutes |

**Key Difference:** `crawl-meetings` populates the meetings database which `crawl-tdocs` uses to know which meetings to crawl TDocs from. Always run `crawl-meetings` at least once before `crawl-tdocs`.

### Query Commands: `query-tdocs` vs `query-meetings`

| Aspect | `query-tdocs` | `query-meetings` |
|--------|---------------|------------------|
| **Returns** | TDoc documents and metadata | Meeting schedules and metadata |
| **Filtering** | By TDoc ID, working group, date range | By meeting ID, working group, date range |
| **Targeted Fetch** | Yes - auto-crawls missing IDs | No - only queries stored data |
| **Output** | Document titles, authors, types | Meeting dates, locations, participants |

**Key Difference:** `query-tdocs` can accept specific TDoc IDs as arguments and will automatically fetch missing TDocs. `query-meetings` only searches the already-crawled meetings database.

## Crawling Commands

### `crawl-tdocs` (alias: `ct`)

```bash
tdoc-crawler crawl-tdocs [OPTIONS]
```

Crawl TDoc metadata from the 3GPP FTP server. TDocs are fetched based on the meetings stored in the database ( populated by `crawl-meetings`).

**When to Use:**

- Initial TDoc metadata population
- Incremental updates to your local TDoc database
- After running `crawl-meetings` to refresh TDoc data

**Options:**

| Option | Description |
|--------|-------------|
| `-c, --cache-dir PATH` | Database and download cache location (default: `~/.tdoc-crawler`) |
| `-w, --working-group WG` | Working groups to crawl (repeatable). Options: `RAN`, `SA`, `CT` |
| `-s, --sub-group SG` | Sub-working groups to crawl (repeatable). Example: `SA4`, `RAN1` |
| `--incremental/--full` | Incremental mode skips existing TDocs; `--full` forces reprocessing |
| `--clear-tdocs` | Clear all TDocs before crawling (start fresh) |
| `--limit-tdocs N` | Maximum number of TDocs to process |
| `--limit-meetings N` | Maximum number of meetings to consider |
| `--limit-meetings-per-wg N` | Maximum meetings per working group |
| `--limit-wgs N` | Maximum number of working groups |
| `--workers N` | Number of parallel workers (default: 4) |
| `--overall-timeout SECONDS` | Maximum total crawl duration |
| `--max-retries N` | HTTP connection retry attempts (default: 3) |
| `--timeout SECONDS` | HTTP request timeout (default: 30) |
| `-v, --verbose` | Enable verbose logging |

**Examples:**

```bash
# Crawl all TDocs from all working groups (after crawl-meetings)
tdoc-crawler crawl-tdocs

# Crawl TDocs for specific working group
tdoc-crawler crawl-tdocs -w SA

# Crawl TDocs for specific subgroup
tdoc-crawler crawl-tdocs -w SA -s S4

# Crawl TDocs from multiple subgroups
tdoc-crawler crawl-tdocs -w RAN -s R1 -s R2

# Crawl TDocs from meetings in date range
tdoc-crawler crawl-tdocs -w SA --start-date 2024-01-01 --end-date 2024-12-31

# Crawl TDocs from specific meeting IDs
tdoc-crawler crawl-tdocs --meeting-ids 60666 60667

# Limit crawl to recent meetings and TDocs
tdoc-crawler crawl-tdocs --limit-meetings-per-wg 5 --limit-tdocs 100

# Crawl with more parallel workers for faster processing
tdoc-crawler crawl-tdocs -w RAN --workers 8

# Force full re-crawl (ignore existing data)
tdoc-crawler crawl-tdocs --full
```

### `crawl-meetings` (alias: `cm`)

```bash
tdoc-crawler crawl-meetings [OPTIONS]
```

Crawl meeting metadata from the 3GPP portal. This command is required before crawling TDocs, as it populates the meetings database that `crawl-tdocs` uses to determine which meetings to crawl.

**When to Use:**

- Initial setup (required before first TDoc crawl)
- Periodic updates to meeting schedules
- Adding new working groups to crawl

**Options:**

| Option | Description |
|--------|-------------|
| `-c, --cache-dir PATH` | Database and download cache location (default: `~/.tdoc-crawler`) |
| `-w, --working-group WG` | Working groups to crawl (repeatable). Options: `RAN`, `SA`, `CT` |
| `-s, --sub-group SG` | Sub-working groups to crawl (repeatable) |
| `--incremental/--full` | Incremental mode skips existing meetings; `--full` forces reprocessing |
| `--clear-db` | Clear all data (meetings and TDocs) before crawling |
| `--limit-meetings N` | Maximum number of meetings overall |
| `--limit-meetings-per-wg N` | Maximum meetings per working group |
| `--limit-wgs N` | Maximum number of working groups |
| `--max-retries N` | HTTP retry attempts (default: 3) |
| `--timeout SECONDS` | HTTP timeout seconds (default: 30) |
| `-v, --verbose` | Enable verbose logging |
| `--eol-username USER` | ETSI Online account username (faster authenticated access) |
| `--eol-password PASS` | ETSI Online account password |
| `--prompt-credentials/--no-prompt-credentials` | Prompt for credentials when missing |

**Examples:**

```bash
# Crawl all meetings for all working groups (initial setup)
tdoc-crawler crawl-meetings

# Crawl meetings for specific working group
tdoc-crawler crawl-meetings -w SA

# Crawl recent meetings only (limit to 10 per working group)
tdoc-crawler crawl-meetings --limit-meetings-per-wg 10

# Update meetings database incrementally
tdoc-crawler crawl-meetings --incremental

# Crawl with ETSI Online credentials for faster access
tdoc-crawler crawl-meetings --eol-username myuser --eol-password mypass

# Crawl specific subgroups
tdoc-crawler crawl-meetings -w RAN -s R1 -s R2
```

## Query Commands

### `query-tdocs` (alias: `qt`)

```bash
tdoc-crawler query-tdocs [TDoc IDs] [OPTIONS]
```

Query TDoc metadata from the local database. If specific TDoc IDs are requested but not found, automatically triggers a targeted crawl to fetch missing data.

**When to Use:**

- Search for specific TDocs by ID
- Filter TDocs by working group, date range
- Export TDoc metadata as JSON or YAML
- Research TDoc history and attributes

**Arguments:**

| Argument | Description |
|----------|-------------|
| `TDoc IDs` | Optional TDoc identifiers to query (repeatable). Example: `R1-2400001` |

**Options:**

| Option | Description |
|--------|-------------|
| `-c, --cache-dir PATH` | Database cache location (default: `~/.tdoc-crawler`) |
| `-w, --working-group WG` | Filter by working group (repeatable) |
| `-o, --output FORMAT` | Output format: `table`, `json`, `yaml` (default: `table`) |
| `-l, --limit N` | Maximum number of results |
| `--order ORDER` | Sort order: `asc` or `desc` (default: `desc`) |
| `--start-date TIMESTAMP` | Filter from ISO 8601 timestamp |
| `--end-date TIMESTAMP` | Filter until ISO 8601 timestamp |
| `--no-fetch` | Disable automatic fetching of missing TDocs |
| `--eol-username USER` | ETSI Online username (for targeted fetch) |
| `--eol-password PASS` | ETSI Online password (for targeted fetch) |

**Automatic Fetch Behavior:**

When you specify TDoc IDs that don't exist in your database, `query-tdocs` automatically:

1. Infers working groups from TDoc ID prefixes (`R*`→RAN, `S*`→SA, `T*`→CT, `C*`→CT)
1. Crawls the 3GPP portal to find meeting information for those TDocs
1. Crawls the FTP server to fetch TDoc metadata
1. Upserts the newly discovered data
1. Returns the complete results

This means you can often get away with just `tdoc-crawler query-tdocs R1-2400001` without manually running `crawl-meetings` and `crawl-tdocs` first.

**Examples:**

```bash
# Query specific TDoc by ID (auto-fetches if missing)
tdoc-crawler query-tdocs R1-2400001

# Query multiple TDocs
tdoc-crawler query-tdocs R1-2400001 S2-2400567 C3-2400123

# Query all TDocs from a working group
tdoc-crawler query-tdocs --working-group RAN

# Query with limit and sorting
tdoc-crawler query-tdocs -w SA --limit 20 --order desc

# Export as JSON
tdoc-crawler query-tdocs R1-2400001 --output json

# Export as YAML
tdoc-crawler query-tdocs -w CT --output yaml

# Filter by date range
tdoc-crawler query-tdocs -w SA --start-date 2024-01-01 --end-date 2024-06-30

# Query without auto-fetch (only search local database)
tdoc-crawler query-tdocs R1-2400001 --no-fetch
```

### `query-meetings` (alias: `qm`)

```bash
tdoc-crawler query-meetings [OPTIONS]
```

Query meeting metadata from the local database. Unlike `query-tdocs`, this command only searches already-crawled meetings and does not trigger automatic fetching.

**When to Use:**

- Browse meeting schedules
- Find meetings by date range
- List meetings for specific working groups
- Export meeting data as JSON or YAML

**Options:**

| Option | Description |
|--------|-------------|
| `-c, --cache-dir PATH` | Database cache location (default: `~/.tdoc-crawler`) |
| `-w, --working-group WG` | Filter by working group (repeatable). Supports aliases: `RP`, `SP`, `CP` |
| `-s, --sub-group SG` | Filter by sub-working group (repeatable) |
| `-o, --output FORMAT` | Output format: `table`, `json`, `yaml` (default: `table`) |
| `-l, --limit N` | Maximum number of results |
| `--order ORDER` | Sort order: `asc` or `desc` (default: `desc`) |
| `--include-without-files` | Include meetings without FTP file links |

**Subgroup Aliases:**

| Alias | Full Name |
|-------|-----------|
| `S1`–`S6` | SA1–SA6 |
| `SP` | SA Plenary |
| `R1`–`R6` | RAN1–RAN6 |
| `RP` | RAN Plenary |
| `C1`–`C6` | CT1–CT6 |
| `CP` | CT Plenary |

**Examples:**

```bash
# List all meetings
tdoc-crawler query-meetings

# Filter by working group
tdoc-crawler query-meetings -w SA

# Filter by subgroup using alias
tdoc-crawler query-meetings -w SA -s S4 --limit 5

# Filter RAN Plenary meetings
tdoc-crawler query-meetings -w RP -s "RAN Plenary" --limit 5

# Filter multiple subgroups
tdoc-crawler query-meetings -w RAN -s R1 -s R2 --limit 10

# Export as JSON
tdoc-crawler query-meetings -w SA --output json

# Export as YAML
tdoc-crawler query-meetings --output yaml

# Include meetings without files
tdoc-crawler query-meetings --include-without-files

# Combine filters
tdoc-crawler query-meetings -w SP -s S4 -s S5 -l 10 -o json
```

## Utility Commands

### `open`

```bash
tdoc-crawler open <TDoc ID> [--cache-dir PATH]
```

Download (if needed), extract, and open a TDoc file with the system default application.

**When to Use:**

- Quickly view a specific TDoc document
- Access TDoc attachments
- Open meeting materials directly from CLI

**Behavior:**

1. Queries the database; if missing, runs targeted crawl workflow
1. Downloads the TDoc into `<cache-dir>/tdocs/`
1. Extracts `.zip` payloads into `<cache-dir>/tdocs/<TDoc ID>/`
1. Opens the first file with the default system application

**Examples:**

```bash
# Open a specific TDoc
tdoc-crawler open R1-2400001

# Open from different cache location
tdoc-crawler open R1-2400001 --cache-dir /path/to/cache
```

### `checkout`

```bash
tdoc-crawler checkout <TDoc IDs...> [--cache-dir PATH] [--force]
```

Download and extract TDoc(s) to a checkout folder (`<cache-dir>/checkout/`) for offline access.

**When to Use:**

- Batch download TDocs for offline review
- Extract meeting materials to a shared location
- Prepare TDoc collections for distribution

**Examples:**

```bash
# Checkout specific TDocs
tdoc-crawler checkout R1-2400001 S2-2400567

# Force re-download even if already checked out
tdoc-crawler checkout R1-2400001 --force

# Checkout to different cache location
tdoc-crawler checkout R1-2400001 --cache-dir /path/to/cache
```

### `stats`

```bash
tdoc-crawler stats [--cache-dir PATH]
```

Display high-level database statistics including TDoc counts per working group, date ranges, and document type distribution.

**When to Use:**

- Check database population status
- Verify crawl results
- Get overview of stored data

**Examples:**

```bash
# View database statistics
tdoc-crawler stats

# View statistics for different cache location
tdoc-crawler stats --cache-dir /path/to/cache
```

## 🚀 HTTP Caching

HTTP caching is **enabled by default** with sensible settings. All HTTP requests are automatically cached to a persistent SQLite database, dramatically improving performance for incremental crawls.

### Default Cache Settings

| Setting | Default Value | Description |
|---------|---------------|-------------|
| TTL | 7200 seconds | Cache lifetime (2 hours) |
| Refresh on access | True | Extends TTL when accessed |
| Cache location | `~/.tdoc-crawler/http-cache.sqlite3` | SQLite database |

### Cache Configuration

**CLI Parameters** (available for `crawl-meetings` and `crawl-tdocs`):

```bash
--cache-ttl INTEGER              # Override TTL (seconds)
--cache-refresh                  # Enable TTL refresh on access
--no-cache-refresh               # Disable TTL refresh
```

**Environment Variables** (add to `.env` file):

```bash
HTTP_CACHE_TTL=7200              # Cache TTL in seconds
HTTP_CACHE_REFRESH_ON_ACCESS=true # Refresh TTL on access
```

### Common Cache Use Cases

#### Development/Testing (Short TTL)

```bash
# 30-minute cache
tdoc-crawler crawl-tdocs --cache-ttl 1800 --working-group RAN
```

#### Production Crawling (Long TTL)

```bash
# 24-hour cache
tdoc-crawler crawl-tdocs --cache-ttl 86400 --working-group SA
```

#### Force Fresh Data

```bash
# Delete cache and rebuild
rm ~/.tdoc-crawler/http-cache.sqlite3
tdoc-crawler crawl-tdocs --working-group CT
```

#### Static Archive (No TTL Refresh)

```bash
# Long TTL, no refresh on access
tdoc-crawler crawl-tdocs --cache-ttl 2592000 --no-cache-refresh
```

### Cache Management

**Check cache status:**

```bash
# Verify cache file exists
ls -lh ~/.tdoc-crawler/http-cache.sqlite3

# View cache statistics
sqlite3 ~/.tdoc-crawler/http-cache.sqlite3 "SELECT COUNT(*) FROM cache;"
```

**Clear cache:**

```bash
# Linux/macOS
rm ~/.tdoc-crawler/http-cache.sqlite3

# Windows PowerShell
Remove-Item "$env:USERPROFILE\.tdoc-crawler\http-cache.sqlite3"
```

**Check cache size:**

```bash
# Linux/macOS
du -h ~/.tdoc-crawler/http-cache.sqlite3

# Windows PowerShell
Get-Item "$env:USERPROFILE\.tdoc-crawler\http-cache.sqlite3" | Select-Object Length
```

### Performance Benefits

- **Initial crawl:** No performance change (cache miss)
- **Incremental crawls:** 50-90% faster (cache hit)
- **Re-validation:** 70-95% faster (cached portal responses)
- **Network traffic:** Reduced by 50-80%

### Cache FAQ

**Q: Do I need to configure anything?**
**A:** No! Default settings work great for most use cases.

**Q: Will this slow down my first crawl?**
**A:** No. First crawl has no performance change. Subsequent crawls are much faster.

**Q: How much disk space does the cache use?**
**A:** Typically 10-50 MB for normal usage. Can grow to 100-200 MB for heavy usage.

**Q: Can I disable caching?**
**A:** Yes, set `--cache-ttl 0` (not recommended) or delete the cache file before each run.

**Q: Does cache respect HTTP headers?**
**A:** Yes! The cache follows RFC 9111 standards and respects Cache-Control headers.

**Q: Is the cache shared between commands?**
**A:** Yes! All commands share the same cache database at `~/.tdoc-crawler/http-cache.sqlite3`
