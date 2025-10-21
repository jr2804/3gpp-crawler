# Review and Improvements for AGENTS.md

**Date:** October 21, 2025
**Reviewer:** GitHub Copilot
**Context:** Post module refactoring (models/ and crawlers/ submodules created)

---

## Executive Summary

After reviewing the current codebase against AGENTS.md, I've identified significant gaps between the documentation and the actual implementation. The main issues are:

1. **Module Structure** - Recent refactoring created `models/` and `crawlers/` submodules not documented in AGENTS.md
2. **Database Schema** - Recent updates added reference tables and foreign keys not described
3. **Missing Implementation Details** - Many critical patterns are missing (targeted fetch, validation caching, etc.)
4. **CLI Commands** - Actual command structure differs from described functionality
5. **Test Patterns** - Shared fixtures and mocking patterns not documented

---

## Critical Missing Information

### 1. Module Structure (CRITICAL)

**Current Reality:**
```
src/tdoc_crawler/
├── models/          # ← NEW: Submodule structure
│   ├── __init__.py
│   ├── base.py
│   ├── working_groups.py
│   ├── subworking_groups.py
│   ├── crawl_limits.py
│   ├── tdocs.py
│   └── meetings.py
├── crawlers/        # ← NEW: Submodule structure
│   ├── __init__.py
│   ├── tdocs.py
│   └── meetings.py
├── database.py
├── cli.py
├── __init__.py
└── __main__.py
```

**What AGENTS.md Says:**
- Mentions `models.py` (singular file) - OUTDATED
- Mentions `crawler.py` (singular file) - OUTDATED
- No mention of submodule structure at all

**Proposed Addition to AGENTS.md:**

Add new section "Project Structure" before "Task":

```markdown
## Project Structure

The project follows a modular architecture with clear separation of concerns:

### Source Code Organization

```
src/tdoc_crawler/
├── models/              # Data models and configuration
│   ├── __init__.py      # Re-exports all public symbols for backward compatibility
│   ├── base.py          # BaseConfigModel, utilities, enums (OutputFormat, SortOrder)
│   ├── working_groups.py  # WorkingGroup enum with tbid/ftp_root properties
│   ├── subworking_groups.py  # SubworkingGroup model
│   ├── crawl_limits.py  # CrawlLimits configuration
│   ├── tdocs.py         # TDocMetadata, TDocRecord, TDocCrawlConfig, QueryConfig
│   └── meetings.py      # MeetingMetadata, MeetingRecord, MeetingCrawlConfig
├── crawlers/            # Web scraping and FTP crawling logic
│   ├── __init__.py      # Re-exports all public symbols (includes TDOC_PATTERN, EXCLUDED_DIRS)
│   ├── tdocs.py         # TDocCrawler - FTP directory traversal, TDoc discovery
│   └── meetings.py      # MeetingCrawler - HTML parsing, date extraction
├── database.py          # SQLite persistence layer with typed wrappers
├── cli.py               # Typer-based CLI with 6 commands
├── __init__.py          # Package initialization
└── __main__.py          # Entry point for `python -m tdoc_crawler`
```

### Module Design Principles

1. **Submodule Re-exports**: Both `models/` and `crawlers/` use `__init__.py` to re-export all public symbols, maintaining backward compatibility
2. **Single Responsibility**: Each file focuses on one concern (e.g., `models/tdocs.py` only contains TDoc-related models)
3. **Type Safety**: All modules use comprehensive type hints with `from __future__ import annotations`
4. **Import Pattern**: Other modules import from `tdoc_crawler.models` and `tdoc_crawler.crawlers`, not from submodules directly

### File Size Guidelines

When splitting modules:
- Base utilities: 20-70 lines
- Model files: 80-150 lines
- Crawler files: 150-350 lines
- CLI file: 600+ lines (acceptable due to command definitions)
- Database file: 900+ lines (acceptable due to schema + queries)
```

---

### 2. Database Schema (CRITICAL)

**Current Reality:**

The database has **5 tables** with foreign key relationships:

```sql
-- Reference tables
working_groups (tbid PK, code, name, ftp_root)
subworking_groups (subtb PK, tbid FK, code, name)

-- Data tables
meetings (meeting_id PK, tbid FK, subtb FK, ...)
tdocs (id PK AUTOINCREMENT, tdoc_id UNIQUE, meeting_id FK, ...)
crawl_log (id PK AUTOINCREMENT, ...)
```

**What AGENTS.md Says:**
- Vague "Design the database schema to efficiently store..."
- No mention of reference tables
- No mention of foreign keys
- No mention of validation caching columns

**Proposed Addition to AGENTS.md:**

Replace "Database Guidelines" section with:

```markdown
## Database Guidelines

### Database Technology

Use SQLite as the embedded database for storing TDoc and meeting metadata. The database should be:
- Single file (default: `~/.tdoc-crawler/tdoc_crawler.db`)
- WAL mode enabled for concurrent reads
- Foreign keys enforced (`PRAGMA foreign_keys = ON`)

### Schema Design

The database consists of 5 tables with normalized reference data:

#### 1. Reference Tables (Static Data)

**`working_groups`** - Master list of 3GPP working groups
```sql
CREATE TABLE working_groups (
    tbid INTEGER PRIMARY KEY NOT NULL,  -- 3GPP technical body ID
    code TEXT NOT NULL UNIQUE,          -- "RAN", "SA", "CT"
    name TEXT NOT NULL,                 -- Full name
    ftp_root TEXT NOT NULL              -- FTP path segment (e.g., "/tsg_ran")
);
```

Populated with:
- RAN (tbid=373, ftp_root="/tsg_ran")
- SA (tbid=375, ftp_root="/tsg_sa")
- CT (tbid=649, ftp_root="/tsg_ct")

**`subworking_groups`** - Master list of subgroups (23 total)
```sql
CREATE TABLE subworking_groups (
    subtb INTEGER PRIMARY KEY NOT NULL,    -- 3GPP sub-technical body ID
    tbid INTEGER NOT NULL,                 -- Parent working group
    code TEXT NOT NULL,                    -- "RP", "R1", "SP", "S1", etc.
    name TEXT NOT NULL,                    -- "RAN Plenary", "RAN1", etc.
    FOREIGN KEY (tbid) REFERENCES working_groups(tbid)
);
CREATE INDEX idx_subworking_groups_tbid ON subworking_groups(tbid);
```

Examples:
- RAN: RP (373), R1-R6 (379, 380, 381, 382, 657, 843)
- SA: SP (375), S1-S6 (384-388, 825)
- CT: CP (649), C1-C6 (651-656)

#### 2. Meetings Table

```sql
CREATE TABLE meetings (
    meeting_id INTEGER PRIMARY KEY NOT NULL UNIQUE,  -- 3GPP meeting ID from portal
    tbid INTEGER NOT NULL,                           -- Working group FK
    subtb INTEGER,                                   -- Subgroup FK (nullable)
    working_group TEXT NOT NULL,                     -- Denormalized for queries
    subgroup TEXT,                                   -- Denormalized for queries
    short_name TEXT NOT NULL,                        -- e.g., "SA4#134"
    title TEXT,                                      -- Full meeting title
    start_date TEXT,                                 -- ISO 8601 date
    end_date TEXT,                                   -- ISO 8601 date
    location TEXT,                                   -- City/venue
    files_url TEXT,                                  -- FTP directory URL
    portal_url TEXT,                                 -- 3GPP portal link
    last_synced TEXT NOT NULL,                       -- UTC timestamp
    created_at TEXT NOT NULL,                        -- Record creation
    updated_at TEXT NOT NULL,                        -- Record update
    FOREIGN KEY (tbid) REFERENCES working_groups(tbid),
    FOREIGN KEY (subtb) REFERENCES subworking_groups(subtb)
);

CREATE INDEX idx_meetings_wg ON meetings(working_group);
CREATE INDEX idx_meetings_tbid ON meetings(tbid);
CREATE INDEX idx_meetings_subtb ON meetings(subtb);
CREATE INDEX idx_meetings_start_date ON meetings(start_date);
```

#### 3. TDocs Table (with Portal Metadata)

```sql
CREATE TABLE tdocs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tdoc_id TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- Case-insensitive unique
    url TEXT NOT NULL,                             -- FTP download URL
    working_group TEXT NOT NULL,                   -- Denormalized
    subgroup TEXT,                                 -- Denormalized
    meeting TEXT,                                  -- Meeting short name
    meeting_id INTEGER,                            -- FK to meetings table
    file_size INTEGER,                             -- Bytes
    -- Portal metadata fields (from validation)
    title TEXT,                                    -- Document title
    contact TEXT,                                  -- Contact person/org
    tdoc_type TEXT,                                -- Document type
    for_purpose TEXT,                              -- Purpose (agreement, discussion, etc.)
    agenda_item TEXT,                              -- Associated agenda item
    status TEXT,                                   -- Document status
    is_revision_of TEXT,                           -- Previous TDoc version
    -- Additional metadata
    document_type TEXT,                            -- Legacy field
    checksum TEXT,                                 -- File hash
    source_path TEXT,                              -- FTP path
    date_created TEXT,                             -- From FTP listing
    date_retrieved TEXT NOT NULL,                  -- UTC timestamp
    date_updated TEXT NOT NULL,                    -- Record update
    -- Validation tracking
    validated BOOLEAN DEFAULT 0,                   -- Portal validation succeeded
    validation_failed BOOLEAN DEFAULT 0,           -- Portal validation failed (cached negative)
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id)
);

CREATE INDEX idx_tdocs_wg ON tdocs(working_group);
CREATE INDEX idx_tdocs_meeting_id ON tdocs(meeting_id);
CREATE INDEX idx_tdocs_date ON tdocs(date_retrieved);
CREATE INDEX idx_tdocs_validated ON tdocs(validated);
CREATE INDEX idx_tdocs_validation_failed ON tdocs(validation_failed);
```

**Validation Caching Logic:**
- When a TDoc is found on FTP but portal validation fails, set `validation_failed=1`
- This prevents repeated portal queries for invalid TDocs
- Only validated TDocs have `validated=1` and populated portal metadata fields

#### 4. Crawl Log Table

```sql
CREATE TABLE crawl_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_type TEXT NOT NULL,              -- "tdocs" or "meetings"
    start_time TEXT NOT NULL,              -- UTC timestamp
    end_time TEXT,                         -- UTC timestamp
    working_groups TEXT NOT NULL,          -- Comma-separated list
    incremental INTEGER NOT NULL,          -- Boolean: 0=full, 1=incremental
    items_added INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    status TEXT NOT NULL                   -- "RUNNING", "COMPLETED", "FAILED"
);
```

### Pydantic Models for Database Entities

Use Pydantic models/dataclasses to represent database entities:

```python
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass

# From models/tdocs.py
@dataclass(frozen=True, kw_only=True)
class TDocMetadata:
    """TDoc metadata retrieved from database queries."""
    tdoc_id: str
    url: str
    working_group: str
    title: str | None = None
    contact: str | None = None
    # ... all other fields from tdocs table

@dataclass(frozen=True, kw_only=True)
class TDocRecord:
    """Complete TDoc database record (includes all fields)."""
    id: int
    tdoc_id: str
    # ... includes id, created_at, updated_at, validated, validation_failed
```

### Database Helper Methods

Implement these essential methods in `TDocDatabase` class:

```python
class TDocDatabase:
    def get_processed_meetings(self) -> set[int]:
        """Return meeting IDs that have been crawled for TDocs."""

    def cache_invalid_tdoc(self, tdoc_id: str, url: str, working_group: str) -> None:
        """Mark TDoc as validation failed to avoid re-checking."""

    def get_cached_invalid_tdocs(self) -> set[str]:
        """Return set of TDoc IDs that failed portal validation."""

    def get_subgroup_by_code(self, code: str) -> tuple[int, int, str] | None:
        """Look up (subtb, tbid, name) by subgroup code."""
```

### Schema Evolution

- Track schema version in `schema_meta` table
- Implement migration scripts for schema changes
- Never break backward compatibility with existing databases
```

---

### 3. Targeted Fetch Feature (CRITICAL)

**Current Reality:**

When users query specific TDoc IDs that aren't in the database, the CLI automatically:
1. Detects missing TDoc IDs
2. Infers working groups from TDoc prefixes (R→RAN, S→SA, T→CT)
3. Creates a `TDocCrawlConfig` with `target_ids` populated
4. Runs a focused crawl for just those TDocs
5. Returns results including newly discovered TDocs

**What AGENTS.md Says:**
- "If TDoc number(s) and/or its metadata are not yet present in the database, the CLI should automatically trigger the crawling process"
- No implementation details provided
- No mention of `target_ids` parameter
- No mention of working group inference

**Proposed Addition to AGENTS.md:**

Add new subsection under "Querying TDoc Metadata":

```markdown
### Automatic Targeted Fetching

When users query specific TDoc IDs that are missing from the database, the CLI automatically fetches them:

#### Implementation Pattern

```python
# In cli.py query command
def _infer_working_groups_from_ids(ids: Iterable[str]) -> list[WorkingGroup]:
    """Extract working group from TDoc ID prefix (R→RAN, S→SA, T→CT)."""
    groups = set()
    for tdoc_id in ids:
        prefix = tdoc_id[0].upper()
        if prefix == "R":
            groups.add(WorkingGroup.RAN)
        elif prefix == "S":
            groups.add(WorkingGroup.SA)
        elif prefix == "T":
            groups.add(WorkingGroup.CT)
    return sorted(groups)

def _fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    missing_ids: list[str],
) -> TDocCrawlResult:
    """Run targeted crawl for specific TDoc IDs."""
    working_groups = _infer_working_groups_from_ids(missing_ids)

    config = TDocCrawlConfig(
        cache_dir=cache_dir,
        working_groups=working_groups,
        target_ids=missing_ids,  # ← Key: limits crawl to these IDs
        incremental=False,        # Always full scan for targeted fetch
        max_retries=3,
        timeout=30,
        verbose=False,
    )

    crawler = TDocCrawler(database)
    return crawler.crawl(config)

def _maybe_fetch_missing_tdocs(
    database: TDocDatabase,
    cache_dir: Path,
    config: QueryConfig,
    results: list[TDocMetadata],
) -> list[TDocMetadata]:
    """Check for missing TDocs and fetch them if needed."""
    # Only trigger if user requested specific IDs
    if not config.tdoc_ids:
        return results

    # Find missing IDs
    found_ids = {r.tdoc_id.upper() for r in results}
    requested_ids = {tid.upper() for tid in config.tdoc_ids}
    missing_ids = requested_ids - found_ids

    if not missing_ids:
        return results

    # Run targeted fetch
    console.print(f"[yellow]Fetching {len(missing_ids)} missing TDocs...")
    fetch_result = _fetch_missing_tdocs(database, cache_dir, sorted(missing_ids))

    # Re-query to include newly fetched TDocs
    return database.query_tdocs(config)
```

#### User Experience

```bash
# User queries TDoc not in database
$ tdoc-crawler query R1-2399999

# CLI automatically:
# 1. Detects R1-2399999 is missing
# 2. Infers working group: RAN (from "R" prefix)
# 3. Triggers targeted crawl: only looks for R1-2399999
# 4. Returns result if found, or reports not found

# Output:
Fetching 1 missing TDoc...
Crawling RAN meetings for targeted TDocs...
Found R1-2399999 in meeting RAN1#118

┌──────────────┬─────────────┬──────────────┐
│ TDoc ID      │ Working Grp │ Title        │
├──────────────┼─────────────┼──────────────┤
│ R1-2399999   │ RAN         │ New Feature  │
└──────────────┴─────────────┴──────────────┘
```

#### Configuration Model

Ensure `TDocCrawlConfig` includes:

```python
@dataclass(frozen=True, kw_only=True)
class TDocCrawlConfig(BaseConfigModel):
    # ... other fields ...
    target_ids: list[str] = field(default_factory=list)  # ← Empty = crawl all

    # When target_ids is populated:
    # - Only TDocs with IDs in this list are upserted
    # - All other discovered files are ignored
    # - Used exclusively for targeted fetch operations
```

#### Crawler Implementation

In `TDocCrawler.crawl()`:

```python
def crawl(self, config: TDocCrawlConfig) -> TDocCrawlResult:
    # ... FTP traversal code ...

    for file_entry in files:
        tdoc_id = extract_tdoc_id(file_entry)

        # Skip if not in target list (when targeting is active)
        if config.target_ids and tdoc_id not in config.target_ids:
            continue

        # Process this TDoc
        # ...
```
```

---

### 4. Validation Caching Pattern (CRITICAL)

**Current Reality:**

The crawler validates TDocs by querying the 3GPP portal. Failed validations are cached to avoid repeated queries:

```python
# Check cache first
invalid_tdocs = database.get_cached_invalid_tdocs()
if tdoc_id in invalid_tdocs:
    continue  # Skip, we know it's invalid

# Try validation
success = validate_tdoc_via_portal(tdoc_id)
if not success:
    # Cache the failure
    database.cache_invalid_tdoc(tdoc_id, url, working_group)
else:
    # Store with portal metadata
    database.upsert_tdoc(tdoc_metadata)
```

**What AGENTS.md Says:**
- "If validation fails, cache the negative result to avoid re-checking"
- No implementation details

**Proposed Addition to AGENTS.md:**

Add new subsection under "Crawling TDocs from Meetings":

```markdown
### Portal Validation and Negative Caching

To avoid repeated failed portal queries, implement negative result caching:

#### Database Support

```python
# In database.py
class TDocDatabase:
    def cache_invalid_tdoc(
        self,
        tdoc_id: str,
        url: str,
        working_group: str,
    ) -> None:
        """Insert TDoc record with validation_failed=1."""
        now = datetime.now(UTC).isoformat()
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO tdocs (
                    tdoc_id, url, working_group, validation_failed,
                    date_retrieved, date_updated
                )
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (tdoc_id.upper(), url, working_group, now, now),
            )
        self.connection.commit()

    def get_cached_invalid_tdocs(self) -> set[str]:
        """Return TDoc IDs that previously failed validation."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT tdoc_id FROM tdocs WHERE validation_failed = 1"
            )
            return {row["tdoc_id"].upper() for row in cursor.fetchall()}
```

#### Crawler Integration

```python
# In crawlers/tdocs.py
class TDocCrawler:
    def crawl(self, config: TDocCrawlConfig) -> TDocCrawlResult:
        # Load invalid cache once at start
        invalid_tdocs = self.database.get_cached_invalid_tdocs()

        for file_entry in ftp_directory_listing:
            tdoc_id = extract_tdoc_id_from_filename(file_entry)

            # Skip if previously failed validation
            if tdoc_id in invalid_tdocs:
                logger.debug(f"Skipping {tdoc_id} (cached as invalid)")
                continue

            # Attempt portal validation
            portal_metadata = self._validate_via_portal(tdoc_id)

            if portal_metadata is None:
                # Validation failed - cache the negative result
                self.database.cache_invalid_tdoc(
                    tdoc_id=tdoc_id,
                    url=ftp_url,
                    working_group=config.working_groups[0].value,
                )
                result.errors.append(f"Validation failed: {tdoc_id}")
            else:
                # Success - store with portal metadata
                self.database.upsert_tdoc(portal_metadata)
                result.inserted += 1
```

#### Force Re-validation

Support `--force-revalidate` flag to bypass cache:

```python
# In cli.py crawl command
@app.command()
def crawl(
    # ... other params ...
    force_revalidate: bool = typer.Option(
        False,
        "--force-revalidate",
        help="Re-validate TDocs even if previously failed",
    ),
) -> None:
    config = TDocCrawlConfig(
        # ... other fields ...
        force_revalidate=force_revalidate,
    )

# In TDocCrawler.crawl()
if not config.force_revalidate:
    invalid_tdocs = self.database.get_cached_invalid_tdocs()
else:
    invalid_tdocs = set()  # Ignore cache, re-validate everything
```
```

---

### 5. CLI Commands Structure (HIGH PRIORITY)

**Current Reality:**

The CLI has **6 commands** with specific signatures:

```python
@app.command()  # Default command name "query"
def query(tdoc_ids, cache_dir, working_group, output_format, limit, order, start_date, end_date)

@app.command("crawl-meetings")  # Explicit name
def crawl_meetings(cache_dir, working_group, incremental, limit_meetings, ...)

@app.command()  # Default command name "crawl"
def crawl(cache_dir, working_group, incremental, limit_tdocs, limit_meetings, ...)

@app.command("query-meetings")
def query_meetings(cache_dir, working_group, subgroup, output_format, limit, order, ...)

@app.command("open")
def open_tdoc(tdoc_id, cache_dir)

@app.command()  # Default command name "stats"
def stats(cache_dir)
```

**What AGENTS.md Says:**
- Lists commands vaguely
- Doesn't specify parameter names
- Doesn't show default values
- Doesn't specify command naming (explicit vs default)

**Proposed Addition to AGENTS.md:**

Add new section after "Main Functionalities":

```markdown
### CLI Commands Implementation

The CLI uses Typer with 6 commands. Follow this exact structure:

#### Command Definitions

```python
# In cli.py
from dotenv import load_dotenv
load_dotenv()  # Load .env at module level, before command execution

app = typer.Typer(help="TDoc crawler - crawl and query structured 3GPP metadata")
console = Console()

# 1. query (default command)
@app.command()
def query(
    tdoc_ids: list[str] | None = typer.Argument(None, help="TDoc identifiers to query"),
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w"),
    output_format: str = typer.Option(OutputFormat.TABLE.value, "--output", "-o"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
    order: str = typer.Option(SortOrder.DESC.value, "--order"),
    start_date: str | None = typer.Option(None, "--start-date"),
    end_date: str | None = typer.Option(None, "--end-date"),
) -> None:
    """Query TDoc metadata with automatic targeted fetch for missing IDs."""
    # Implementation includes _maybe_fetch_missing_tdocs()

# 2. crawl (TDocs from FTP)
@app.command()
def crawl(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w"),
    incremental: bool = typer.Option(True, "--incremental/--full"),
    limit_tdocs: int | None = typer.Option(None, "--limit-tdocs"),
    limit_meetings: int | None = typer.Option(None, "--limit-meetings"),
    limit_meetings_per_wg: int | None = typer.Option(None, "--limit-meetings-per-wg"),
    limit_wgs: int | None = typer.Option(None, "--limit-wgs"),
    max_retries: int = typer.Option(3, "--max-retries"),
    timeout: int = typer.Option(30, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Crawl FTP server for TDocs. Requires meetings DB to be populated first."""
    # Check if meetings exist, show error if not

# 3. crawl-meetings (from portal)
@app.command("crawl-meetings")
def crawl_meetings(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w"),
    incremental: bool = typer.Option(True, "--incremental/--full"),
    limit_meetings: int | None = typer.Option(None, "--limit-meetings"),
    limit_meetings_per_wg: int | None = typer.Option(None, "--limit-meetings-per-wg"),
    limit_wgs: int | None = typer.Option(None, "--limit-wgs"),
    max_retries: int = typer.Option(3, "--max-retries"),
    timeout: int = typer.Option(30, "--timeout"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    eol_username: str | None = typer.Option(None, "--eol-username"),
    eol_password: str | None = typer.Option(None, "--eol-password"),
    prompt_credentials: bool = typer.Option(True, "--prompt-credentials/--no-prompt-credentials"),
) -> None:
    """Crawl 3GPP portal for meeting metadata."""

# 4. query-meetings
@app.command("query-meetings")
def query_meetings(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c"),
    working_group: list[str] | None = typer.Option(None, "--working-group", "-w"),
    subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s"),
    output_format: str = typer.Option(OutputFormat.TABLE.value, "--output", "-o"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
    order: str = typer.Option(SortOrder.DESC.value, "--order"),
    include_without_files: bool = typer.Option(False, "--include-without-files"),
) -> None:
    """Query stored meeting metadata."""

# 5. open
@app.command("open")
def open_tdoc(
    tdoc_id: str = typer.Argument(..., help="TDoc identifier to download and open"),
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c"),
) -> None:
    """Download, unzip, and open TDoc in system default application."""
    # Implements _download_to_path(), _prepare_tdoc_file(), _launch_file()

# 6. stats
@app.command()
def stats(
    cache_dir: Path = typer.Option(Path.home() / ".tdoc-crawler", "--cache-dir", "-c"),
) -> None:
    """Display database statistics (total TDocs, by working group, date range)."""
```

#### Helper Functions (Required)

```python
def _database_path(cache_dir: Path) -> Path:
    """Standard database path: <cache_dir>/tdoc_crawler.db"""
    return cache_dir / "tdoc_crawler.db"

def _parse_working_groups(values: list[str] | None) -> list[WorkingGroup]:
    """Parse and normalize WG names, expand plenary aliases (RP→RAN, SP→SA, CP→CT)."""
    # Uses normalize_working_group_alias() from crawlers module

def _parse_subgroups(values: list[str] | None) -> list[str]:
    """Parse and normalize subgroup codes, expand plenary aliases."""
    # Uses normalize_subgroup_alias() from crawlers module

def _infer_working_groups_from_ids(ids: Iterable[str]) -> list[WorkingGroup]:
    """Extract working group from TDoc ID prefix (R→RAN, S→SA, T→CT)."""

def _download_to_path(url: str, destination: Path) -> None:
    """Download file from URL to local path."""

def _prepare_tdoc_file(metadata: TDocMetadata, cache_dir: Path) -> Path:
    """Download, unzip TDoc, return path to first file in extracted directory."""

def _launch_file(path: Path) -> None:
    """Open file in system default application (OS-specific logic)."""

def _fetch_missing_tdocs(...) -> TDocCrawlResult:
    """Run targeted crawl for specific missing TDoc IDs."""

def _maybe_fetch_missing_tdocs(...) -> list[TDocMetadata]:
    """Check for missing TDocs in query results and fetch if needed."""
```

#### Default Values Reference

| Parameter | Default Value | Notes |
|-----------|---------------|-------|
| `cache_dir` | `Path.home() / ".tdoc-crawler"` | All commands |
| `incremental` | `True` | crawl, crawl-meetings |
| `max_retries` | `3` | crawl, crawl-meetings |
| `timeout` | `30` | crawl, crawl-meetings |
| `output_format` | `OutputFormat.TABLE.value` | query, query-meetings |
| `order` | `SortOrder.DESC.value` | query, query-meetings |
| `verbose` | `False` | crawl, crawl-meetings |
| `prompt_credentials` | `True` | crawl-meetings |
| `include_without_files` | `False` | query-meetings |
| `working_group` | `None` (= all WGs) | Parsed by `_parse_working_groups()` |
```

---

### 6. Test Patterns and Fixtures (HIGH PRIORITY)

**Current Reality:**

Tests use shared pytest fixtures defined in `tests/conftest.py`:

```python
@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create temporary cache directory."""

@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
    """Get test database path."""

@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
    """Create sample TDoc metadata for testing."""

@pytest.fixture
def sample_meetings() -> list[MeetingMetadata]:
    """Create sample meeting metadata for testing."""
```

**What AGENTS.md Says:**
- "Use fixtures and parameterized tests to reduce code duplication"
- No mention of standard fixtures
- No mention of mock patterns

**Proposed Addition to AGENTS.md:**

Replace "Testing" section with:

```markdown
## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_cli.py          # CLI command tests (12 tests)
├── test_crawler.py      # Crawler logic tests (10 tests)
├── test_database.py     # Database operations tests (13 tests)
├── test_models.py       # Pydantic model tests (10 tests)
├── test_targeted_fetch.py  # Targeted fetch feature tests (12 tests)
└── data/                # Test data files
    └── README.md
```

### Standard Fixtures (tests/conftest.py)

```python
import pytest
from pathlib import Path
from tdoc_crawler.models import TDocMetadata, MeetingMetadata, WorkingGroup

@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory for tests.

    Returns:
        Path to test cache directory (e.g., /tmp/pytest-xxx/test-cache)
    """
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
    """Get test database path.

    Returns:
        Path to test database (test-cache/tdoc_crawler.db)
    """
    return test_cache_dir / "tdoc_crawler.db"

@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
    """Create sample TDoc metadata for testing.

    Returns:
        List of 2 sample TDocMetadata instances with realistic data
    """
    return [
        TDocMetadata(
            tdoc_id="R1-2301234",
            url="https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/.../R1-2301234.zip",
            working_group="RAN",
            subgroup="RAN1",
            title="Sample TDoc Title",
            date_retrieved=datetime.now(UTC).isoformat(),
            date_updated=datetime.now(UTC).isoformat(),
        ),
        TDocMetadata(
            tdoc_id="S2-2305678",
            url="https://www.3gpp.org/ftp/tsg_sa/WG2_Arch/.../S2-2305678.zip",
            working_group="SA",
            subgroup="SA2",
            title="Another Sample TDoc",
            date_retrieved=datetime.now(UTC).isoformat(),
            date_updated=datetime.now(UTC).isoformat(),
        ),
    ]

@pytest.fixture
def sample_meetings() -> list[MeetingMetadata]:
    """Create sample meeting metadata for testing.

    Returns:
        List of 2 sample MeetingMetadata instances
    """
    return [
        MeetingMetadata(
            meeting_id=123,
            working_group="RAN",
            subgroup="RAN1",
            short_name="RAN1#118",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 19),
            location="Athens, Greece",
            files_url="https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_118/Docs/",
            last_synced=datetime.now(UTC).isoformat(),
        ),
        # ... another meeting
    ]
```

### Mock Patterns

#### Mocking FTP Connections

```python
from unittest.mock import MagicMock, patch

@patch("tdoc_crawler.crawlers.tdocs.FTP")  # Note: patch in crawlers.tdocs, not crawler
def test_crawl_collects_tdocs(
    mock_ftp_class: MagicMock,
    test_db_path: Path,
) -> None:
    """Test FTP crawling with mocked connection."""
    # Setup mock FTP responses
    listing = ["-rw-r--r-- 1 ftp ftp 2048 Jan 01 2024 R1-2301234.zip"]

    ftp_instance = MagicMock()
    def retrlines(command: str, callback) -> None:
        if command != "LIST":
            raise AssertionError
        for entry in listing:
            callback(entry)

    ftp_instance.retrlines.side_effect = retrlines
    mock_ftp_class.return_value = ftp_instance

    # Run test
    with TDocDatabase(test_db_path) as database:
        crawler = TDocCrawler(database)
        config = TDocCrawlConfig(
            cache_dir=test_db_path.parent,
            working_groups=[WorkingGroup.RAN],
            incremental=False,
        )
        result = crawler.crawl(config)

    assert result.processed == 1
```

**IMPORTANT:** After module refactoring, FTP must be patched at:
- `tdoc_crawler.crawlers.tdocs.FTP` (NOT `tdoc_crawler.crawler.FTP`)

#### Mocking Database

```python
@patch("tdoc_crawler.cli.TDocDatabase")
def test_query_command(
    mock_db_class: MagicMock,
    test_cache_dir: Path,
    sample_tdocs: list[TDocMetadata],
) -> None:
    """Test CLI query command with mocked database."""
    mock_db_instance = MagicMock()
    mock_db_instance.query_tdocs.return_value = sample_tdocs
    mock_db_class.return_value.__enter__.return_value = mock_db_instance

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "R1-2301234", "--cache-dir", str(test_cache_dir)],
    )

    assert result.exit_code == 0
    assert "R1-2301234" in result.stdout
```

### Test Categories

#### 1. Unit Tests (test_models.py, test_database.py)
- Test individual functions and classes in isolation
- Use real database for database tests (fast with SQLite)
- Cover all Pydantic validation logic

#### 2. Integration Tests (test_crawler.py)
- Test crawler logic with mocked FTP/HTTP
- Test database interactions
- Cover error handling and retries

#### 3. End-to-End Tests (test_cli.py)
- Test full CLI commands using `typer.testing.CliRunner`
- Mock external dependencies (FTP, HTTP, database)
- Verify user-facing output

#### 4. Feature Tests (test_targeted_fetch.py)
- Test complex features like targeted fetch
- Test working group inference
- Test automatic fetch triggering

### Coverage Goals

- Aim for 70%+ overall coverage
- Prioritize critical paths (crawlers, database operations)
- CLI commands: 60%+ (some branches are error paths)
- Models: 90%+ (Pydantic validation)
- Database: 70%+ (complex queries, error handling)

### Running Tests

```bash
# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=src/tdoc_crawler --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_cli.py -v

# Run specific test
uv run pytest tests/test_cli.py::TestQueryCommand::test_query_specific_tdoc -v
```
```

---

### 7. Missing Implementation Details

**Current Reality:**

Several critical implementation patterns are used but not documented:

1. **Working Group Alias Normalization**
   - `RP` → `RAN` (RAN Plenary)
   - `SP` → `SA` (SA Plenary)
   - `CP` → `CT` (CT Plenary)

2. **Subgroup Alias Normalization**
   - `R1-R6`, `S1-S6`, `C1-C6` → Corresponding subgroups
   - Case-insensitive matching

3. **Date Parsing for Meetings**
   - Multiple formats: "15-19 Jan 2024", "15 Jan - 19 Jan 2024", "15 January 2024"
   - Handles single-day and multi-day meetings

4. **FTP Directory Exclusions**
   - Exclude: `["Inbox", "Outbox", "Archive", "Old"]`
   - Pattern: `TDOC_PATTERN = re.compile(r"^[RSTC]\d+-\d+", re.IGNORECASE)`

**Proposed Addition:**

Add new section "Implementation Patterns":

```markdown
## Implementation Patterns

### Working Group Alias Handling

Users often refer to plenary groups using shorthand codes. Normalize these:

```python
# In crawlers/meetings.py
PLENARY_ALIASES = {
    "RP": "RAN",  # RAN Plenary
    "SP": "SA",   # SA Plenary
    "CP": "CT",   # CT Plenary
}

def normalize_working_group_alias(value: str) -> str:
    """Expand plenary alias (RP→RAN) or return uppercase input."""
    upper = value.upper().strip()
    return PLENARY_ALIASES.get(upper, upper)

def normalize_subgroup_alias(value: str) -> str:
    """Expand plenary alias and validate against known subgroups."""
    normalized = normalize_working_group_alias(value)
    # If it's a plenary alias, append "P" (RP→RP, SP→SP, CP→CP)
    if value.upper() in PLENARY_ALIASES:
        return value.upper()  # Keep original form
    return normalized
```

Usage in CLI:
```python
# User types: --working-group RP
# Parsed as: WorkingGroup.RAN

# User types: --sub-group RP
# Stored as: "RP" (RAN Plenary code)
```

### FTP Directory Filtering

Exclude non-meeting directories when crawling:

```python
# In crawlers/tdocs.py
EXCLUDED_DIRS = ["Inbox", "Outbox", "Archive", "Old"]
TDOC_PATTERN = re.compile(r"^[RSTC]\d+-\d+", re.IGNORECASE)

def _should_skip_directory(dir_name: str) -> bool:
    """Check if directory should be excluded from crawl."""
    return any(excl.lower() in dir_name.lower() for excl in EXCLUDED_DIRS)

def _is_tdoc_file(filename: str) -> bool:
    """Check if filename matches TDoc pattern."""
    stem = Path(filename).stem
    return TDOC_PATTERN.match(stem) is not None
```

### Meeting Date Parsing

Handle multiple date formats from 3GPP portal HTML:

```python
# In crawlers/meetings.py
DATE_PATTERN = re.compile(
    r"(\d{1,2})\s*(?:-\s*(\d{1,2}))?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+"
    r"(\d{4})"
)

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

def _parse_meeting_date(date_str: str) -> tuple[date | None, date | None]:
    """
    Parse date string into (start_date, end_date).

    Examples:
        "15-19 Jan 2024" → (2024-01-15, 2024-01-19)
        "15 Jan 2024" → (2024-01-15, None)
        "15 January - 19 January 2024" → (2024-01-15, 2024-01-19)
    """
    match = DATE_PATTERN.search(date_str)
    if not match:
        return (None, None)

    start_day, end_day, month_str, year = match.groups()
    month = MONTH_MAP[month_str.lower()[:3]]

    start_date = date(int(year), month, int(start_day))
    end_date = date(int(year), month, int(end_day)) if end_day else None

    return (start_date, end_date)
```

### TDoc ID Normalization

Always uppercase and strip whitespace:

```python
# In models/base.py
def _normalize_tdoc_ids(ids: Iterable[str]) -> list[str]:
    """Uppercase and strip whitespace from TDoc identifiers."""
    return sorted({tid.strip().upper() for tid in ids})

# Usage in models
@dataclass(frozen=True, kw_only=True)
class QueryConfig(BaseConfigModel):
    tdoc_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tdoc_ids", _normalize_tdoc_ids(self.tdoc_ids))
```

### Error Handling Pattern

Use Rich console for user-friendly error messages:

```python
from rich.console import Console
console = Console()

try:
    # Operation
except SomeSpecificError as exc:
    console.print(f"[red]Operation failed: {exc}[/red]")
    raise typer.Exit(code=1) from exc
```

Error Exit Codes:
- `0` - Success
- `1` - General error (file not found, operation failed)
- `2` - Invalid input (bad date format, unknown working group)
```

---

## Structural Improvements

### 1. Organization

**Current:** AGENTS.md has sections scattered throughout

**Proposed:** Reorganize into logical groups:

```markdown
1. General Coding Guidelines
2. Background on 3GPP, TDocs and Meetings
3. Project Structure (NEW)
4. Task & Main Functionalities
5. Implementation Patterns (NEW)
6. Database Guidelines (EXPANDED)
7. CLI Commands Implementation (NEW)
8. Python-Specific Guidelines
9. Testing Guidelines (EXPANDED)
10. Documentation
```

### 2. Add "Quick Start for Assistants"

Add at the very beginning:

```markdown
## Quick Start for Coding Assistants

Before implementing features, review these critical sections:

1. **Project Structure** - Understand the models/ and crawlers/ submodule organization
2. **Database Schema** - Review the 5-table structure with foreign keys
3. **CLI Commands** - Study the exact command signatures and defaults
4. **Implementation Patterns** - Learn targeted fetch, validation caching, alias normalization
5. **Test Patterns** - Use standard fixtures and mock patterns

**Key Files to Examine First:**
- `src/tdoc_crawler/cli.py` - All 6 CLI commands
- `src/tdoc_crawler/database.py` - Schema and queries
- `src/tdoc_crawler/models/__init__.py` - All data models
- `src/tdoc_crawler/crawlers/__init__.py` - Crawler implementations
- `tests/conftest.py` - Shared test fixtures
```

---

## Priority Recommendations

### Must Fix (Critical)

1. **Add "Project Structure" section** - Document models/ and crawlers/ submodules
2. **Expand "Database Guidelines"** - Full schema with all 5 tables
3. **Add "CLI Commands Implementation"** - Exact signatures and defaults
4. **Add "Targeted Fetch Feature"** - Implementation with code examples
5. **Add "Validation Caching Pattern"** - Negative result caching

### Should Fix (High Priority)

6. **Add "Implementation Patterns"** - Alias normalization, date parsing, FTP filtering
7. **Expand "Testing Guidelines"** - Standard fixtures, mock patterns
8. **Add "Quick Start for Assistants"** - Navigation guide at the top

### Nice to Have (Medium Priority)

9. **Add example workflows** - "How to add a new CLI command"
10. **Add troubleshooting section** - Common issues and solutions
11. **Add performance guidelines** - Parallel processing, caching strategies

---

## Validation Checklist

After updating AGENTS.md, verify:

- [ ] All current module paths are correct (models/, crawlers/, not models.py, crawler.py)
- [ ] All 5 database tables are documented with full schemas
- [ ] All 6 CLI commands have exact signatures
- [ ] Targeted fetch workflow is explained with code
- [ ] Validation caching is explained with code
- [ ] Standard test fixtures are documented
- [ ] FTP patch paths reference crawlers.tdocs, not crawler
- [ ] All default values match actual code
- [ ] Working group aliases (RP→RAN, etc.) are documented

---

## Example: Before and After

### Before (Current AGENTS.md)

```markdown
## Database Guidelines

- Use SQLite as the database for storing TDoc and meeting metadata.
- Design the database schema to efficiently store and query TDoc and meeting metadata.
- Use appropriate indexing to optimize query performance.
```

### After (Proposed)

```markdown
## Database Guidelines

### Database Technology

Use SQLite as the embedded database. Configuration:
- File: `<cache_dir>/tdoc_crawler.db`
- WAL mode: `PRAGMA journal_mode = WAL`
- Foreign keys: `PRAGMA foreign_keys = ON`

### Schema (5 Tables)

#### Reference Tables
- `working_groups` (tbid PK, code, name, ftp_root)
- `subworking_groups` (subtb PK, tbid FK, code, name)

#### Data Tables
- `meetings` (meeting_id PK, tbid FK, subtb FK, ...)
- `tdocs` (id PK, tdoc_id UNIQUE, meeting_id FK, validated, validation_failed, ...)
- `crawl_log` (id PK, ...)

[Full schemas with CREATE TABLE statements...]

### Helper Methods

```python
class TDocDatabase:
    def get_processed_meetings(self) -> set[int]: ...
    def cache_invalid_tdoc(self, tdoc_id, url, working_group): ...
    def get_cached_invalid_tdocs(self) -> set[str]: ...
```
```

---

## Conclusion

The current AGENTS.md provides good general guidelines but lacks critical implementation details needed to regenerate the codebase accurately. The most important additions are:

1. **Module structure documentation** (models/ and crawlers/ submodules)
2. **Complete database schema** (all 5 tables with relationships)
3. **CLI command signatures** (exact parameters and defaults)
4. **Feature implementations** (targeted fetch, validation caching)
5. **Test patterns** (standard fixtures, mock approaches)

With these additions, coding assistants will have sufficient information to recreate the project from scratch or add new features consistently with the existing architecture.

---

**Next Steps:**

1. Review this document with the development team
2. Prioritize which sections to add first (recommend: structure, database, CLI)
3. Update AGENTS.md incrementally
4. Validate each update by attempting code regeneration
5. Keep AGENTS.md synchronized with future refactorings
