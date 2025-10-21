# TDoc Crawler – Quick Reference

Single source of truth for the CLI behaviour. All examples assume execution from the project root.

## Shared Behaviour

- Cache files and the SQLite database default to `~/.tdoc-crawler`; override with `--cache-dir`.
- Incremental crawls skip IDs already stored; pass `--full` to force reprocessing.
- Queries that specify `tdoc_ids` automatically launch a targeted crawl when a requested ID is missing; results refresh before output.
- Targeted crawls infer working groups from the prefix of each TDoc ID (`R`, `S`, `T`, `C`).
- Downloaded TDocs live under `<cache-dir>/tdocs/` and are reused when possible.

## Commands

### `crawl-meetings`

```bash
uv run tdoc-crawler crawl-meetings [OPTIONS]
```

Scrape the 3GPP portal for meeting metadata. **Run this first** to populate the meetings database before crawling TDocs.

**Options:**

- `-c, --cache-dir PATH` – Database and download cache location.
- `-w, --working-group WG` – Repeatable; defaults to all (`RAN`, `SA`, `CT`).
- `--full/--incremental` – Disable incremental mode (defaults to incremental).
- `--limit-meetings`, `--limit-meetings-per-wg`, `--limit-wgs` – Throttle traversal.
- `--eol-username`, `--eol-password` – ETSI Online credentials (or use `EOL_USERNAME`/`EOL_PASSWORD` env vars).
- `-v, --verbose` – Emit debug logging.

**Examples:**

```bash
# Crawl all meetings for all working groups (initial setup)
uv run tdoc-crawler crawl-meetings

# Crawl meetings for specific working group
uv run tdoc-crawler crawl-meetings -w SA

# Crawl recent meetings only (limit to 10 per working group)
uv run tdoc-crawler crawl-meetings --limit-meetings-per-wg 10

# Update meetings database incrementally
uv run tdoc-crawler crawl-meetings --incremental
```

### `crawl`

```bash
uv run tdoc-crawler crawl [OPTIONS]
```

Crawl the 3GPP FTP hierarchy for TDocs and upsert metadata. **Requires meetings database** to be populated first via `crawl-meetings`.

**Options:**

- `-c, --cache-dir PATH` – Database and download cache location.
- `-w, --working-group WG` – Repeatable; defaults to all (`RAN`, `SA`, `CT`).
- `-s, --sub-group SG` – Filter by sub-working group (repeatable). Supports aliases like `S4` (SA4), `R1` (RAN1).
- `--full/--incremental` – Disable incremental mode (defaults to incremental).
- `--limit-tdocs`, `--limit-meetings`, `--limit-meetings-per-wg`, `--limit-wgs` – Throttle traversal.
- `--start-date`, `--end-date` – ISO 8601 date range filter for meetings (e.g., `2024-01-01`).
- `--meeting-ids` – Specific meeting IDs to crawl (repeatable).
- `--workers` – Number of parallel workers (default: 4).
- `--max-retries`, `--timeout` – FTP connection controls.
- `-v, --verbose` – Emit debug logging.

**Examples:**

```bash
# Crawl all TDocs from all working groups (after crawl-meetings)
uv run tdoc-crawler crawl

# Crawl TDocs for specific working group
uv run tdoc-crawler crawl -w SA

# Crawl TDocs for specific subgroup
uv run tdoc-crawler crawl -w SA -s S4

# Crawl TDocs from multiple subgroups
uv run tdoc-crawler crawl -w RAN -s R1 -s R2

# Crawl TDocs from meetings in date range
uv run tdoc-crawler crawl -w SA --start-date 2024-01-01 --end-date 2024-12-31

# Crawl TDocs from specific meeting IDs
uv run tdoc-crawler crawl --meeting-ids 60666 60667

# Limit crawl to recent meetings and TDocs
uv run tdoc-crawler crawl --limit-meetings-per-wg 5 --limit-tdocs 100

# Crawl with more parallel workers for faster processing
uv run tdoc-crawler crawl -w RAN --workers 8
```

### `query`

```bash
uv run tdoc-crawler query [TDoc IDs] [OPTIONS]
```

Display stored TDoc metadata in table (default), JSON, or YAML.

- `-w, --working-group WG` – Filter by working group.
- `-o, --output {table,json,yaml}` – Choose output format.
- `-l, --limit INT` – Cap result count.
- `--order {asc,desc}` – Sort by `date_retrieved`.
- `--start-date`, `--end-date` – ISO 8601 timestamps for range filtering.
- **Targeted fetch:** When specific IDs are requested but absent, the CLI triggers a targeted crawl (non-incremental, `target_ids` populated). Newly discovered TDocs are upserted before the final output. Failures are reported, and unresolved IDs are highlighted.

### `open`

```bash
uv run tdoc-crawler open <TDoc ID> [--cache-dir PATH]
```

Download (if needed), extract, and launch a TDoc with the system default application.

1. Queries the database; if missing, runs the same targeted crawl workflow as `query`.
2. Downloads the TDoc into `<cache-dir>/tdocs/`, only accepting `ftp://`, `http://`, or `https://` URLs.
3. `.zip` payloads are extracted into `<cache-dir>/tdocs/<TDoc ID>/`; the first file encountered is opened.
4. Non-archive payloads are saved once and reused.
5. Launches via `os.startfile` on Windows, `open` on macOS, or `xdg-open` on Linux. Errors halt the command with a non-zero exit code.

### `query-meetings`

```bash
uv run tdoc-crawler query-meetings [OPTIONS]
```

List stored meeting metadata.

- `-w, --working-group WG` – Filter by working group. Supports aliases: `RP` (RAN), `SP` (SA), `CP` (CT).
- `-s, --sub-group SG` – Filter by sub-working group (repeatable). Supports aliases like `S4` (SA4), `R1` (RAN1), `RP` (RAN Plenary).
- `-o, --output {table,json,yaml}` – Choose output format.
- `-l, --limit INT` – Cap results.
- `--order {asc,desc}` – Sort by start date.
- `--include-without-files` – Include meetings lacking FTP links.

**Supported Subgroup Aliases:**

- **SA:** `S1`→`SA1`, `S2`→`SA2`, `S3`→`SA3`, `S4`→`SA4`, `S5`→`SA5`, `S6`→`SA6`, `SP`→`SA Plenary`
- **RAN:** `R1`→`RAN1`, `R2`→`RAN2`, `R3`→`RAN3`, `R4`→`RAN4`, `R5`→`RAN5`, `R6`→`RAN6`, `RP`→`RAN Plenary`
- **CT:** `C1`→`CT1`, `C2`→`CT2`, `C3`→`CT3`, `C4`→`CT4`, `C5`→`CT5`, `C6`→`CT6`, `CP`→`CT Plenary`

**Examples:**

```bash
# Filter by SA working group and SA4 subgroup (using alias)
uv run tdoc-crawler query-meetings -w SA -s S4 --limit 5

# Filter RAN Plenary meetings (using working group alias)
uv run tdoc-crawler query-meetings -w RP -s "RAN Plenary" --limit 5

# Filter multiple subgroups
uv run tdoc-crawler query-meetings -w RAN -s R1 -s R2 --limit 10

# Combine aliases
uv run tdoc-crawler query-meetings -w SP -s S4 --limit 5
```

### `stats`

```bash
uv run tdoc-crawler stats [--cache-dir PATH]
```

Show high-level database statistics (counts per working group, date range, etc.).
