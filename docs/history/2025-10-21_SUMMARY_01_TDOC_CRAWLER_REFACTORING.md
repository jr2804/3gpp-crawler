# 3GPP Crawler Refactoring Plan

**Date:** 2025-10-21
**Type:** Major Refactoring

## Problem Statement

The current 3GPP crawler has fundamental design flaws:

1. Parses FTP directory listings expecting 9 tokens (HTML table format) when FTP LIST returns 4-5 tokens
1. Uses brute-force FTP crawling instead of meeting-driven approach
1. No portal validation of TDoc candidates
1. No parallel processing support
1. No caching of negative results

## New Architecture

### Core Principle: Meeting-Driven TDoc Crawling

TDoc crawling must depend on meeting metadata. The workflow is:

```
1. User runs `crawl-meetings` → Populates meetings table
2. User runs `crawl` → Queries meetings table → Crawls each meeting's files_url
3. For each candidate file → Validate via portal → Store/cache result
```

## Changes Required

### 1. Models (`src/tdoc_crawler/models.py`)

**Updated:**

- ✅ `TDocMetadata`: Added portal fields (title, contact, tdoc_type, for_purpose, agenda_item, status, is_revision_of, validated, validation_failed)
- ✅ `TDocRecord`: Updated to match TDocMetadata fields
- ✅ `TDocCrawlConfig`: Added subgroups, meeting_ids, start_date, end_date, force_revalidate, workers, credentials

### 2. Database Schema (`src/tdoc_crawler/database.py`)

**TODO:** Update tdocs table schema:

```sql
CREATE TABLE IF NOT EXISTS tdocs (
    tdoc_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    working_group TEXT NOT NULL,
    subgroup TEXT,
    meeting TEXT,
    meeting_id INTEGER,
    file_size INTEGER,

    -- Portal metadata
    title TEXT,
    contact TEXT,
    tdoc_type TEXT,
    for_purpose TEXT,
    agenda_item TEXT,
    status TEXT,
    is_revision_of TEXT,

    -- Legacy/system fields
    document_type TEXT,
    checksum TEXT,
    source_path TEXT,
    date_created TIMESTAMP,
    date_retrieved TIMESTAMP NOT NULL,
    date_updated TIMESTAMP NOT NULL,
    validated BOOLEAN DEFAULT 0,
    validation_failed BOOLEAN DEFAULT 0,

    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id)
)
```

**TODO:** Add methods:

- `get_processed_meetings(working_groups, subgroups) -> set[int]`: Returns meeting IDs already processed
- `cache_invalid_tdoc(tdoc_id)`: Cache negative validation result
- `get_cached_invalid_tdocs() -> set[str]`: Get list of known invalid TDocs

### 3. Portal Parsing (`src/tdoc_crawler/portal.py`) - NEW FILE

**TODO:** Create new module for portal interactions:

```python
def fetch_tdoc_metadata(
    tdoc_id: str,
    credentials: PortalCredentials | None = None,
    timeout: int = 30
) -> dict | None:
    """Fetch and parse TDoc metadata from 3GPP portal.

    Args:
        tdoc_id: TDoc identifier (e.g., 'S4-251364')
        credentials: Optional portal credentials
        timeout: Request timeout in seconds

    Returns:
        Dictionary with parsed fields or None if validation fails
    """
    url = f"https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid={tdoc_id}"

    # Handle login redirect if needed
    response = requests.get(url, timeout=timeout, allow_redirects=True)

    if "login.aspx" in response.url.lower():
        if credentials is None:
            logger.warning(f"Portal requires authentication for {tdoc_id}")
            return None
        # TODO: Implement login flow

    if response.status_code != 200:
        return None

    return parse_tdoc_portal_page(response.text)


def parse_tdoc_portal_page(html: str) -> dict | None:
    """Parse TDoc metadata from portal HTML.

    Expected fields (from table/form structure):
    - Meeting (required)
    - Title (required)
    - Contact (required)
    - TDoc type (required)
    - For (required)
    - Agenda item (required)
    - Status (required)
    - Is revision of (optional)
    """
    soup = BeautifulSoup(html, "lxml")

    # TODO: Analyze HTML structure and implement parsing
    # Pattern: likely <label>Field Name</label> followed by <input> or <span>

    metadata = {}
    required_fields = ["meeting", "title", "contact", "tdoc_type", "for_purpose", "agenda_item", "status"]

    # Parse each field
    # ...

    # Validate required fields present
    if not all(metadata.get(field) for field in required_fields):
        return None

    return metadata
```

### 4. 3GPP Crawler Refactoring (`src/tdoc_crawler/crawler.py`)

**TODO:** Complete rewrite of `TDocCrawler.crawl()`:

```python
def crawl(self, config: TDocCrawlConfig) -> TDocCrawlResult:
    """Execute meeting-driven TDoc crawl."""

    # Step 1: Check meetings available
    meetings = self.database.query_meetings(MeetingQueryConfig(
        working_groups=config.working_groups,
        subgroups=config.subgroups,
        # ... filter by meeting_ids, dates, etc.
    ))

    if not meetings:
        raise ValueError(
            "No meetings available. Run 'crawl-meetings' first to populate meeting metadata."
        )

    # Step 2: Filter meetings based on incremental mode
    if config.incremental and not config.force_revalidate:
        processed = self.database.get_processed_meetings(config.working_groups, config.subgroups)
        meetings = [m for m in meetings if m.meeting_id not in processed]

    # Step 3: Parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = []
        for meeting in meetings:
            if not meeting.files_url:
                logger.debug(f"Meeting {meeting.short_name} has no files_url, skipping")
                continue

            future = executor.submit(self._crawl_meeting, meeting, config)
            futures.append(future)

        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                # Aggregate results
            except Exception as exc:
                logger.error(f"Meeting crawl failed: {exc}")

    return TDocCrawlResult(...)


def _crawl_meeting(self, meeting: MeetingMetadata, config: TDocCrawlConfig) -> list[TDocMetadata]:
    """Crawl a single meeting's files_url."""

    collected = []

    try:
        # List files at files_url (FTP or HTTP)
        files = self._list_files_at_url(meeting.files_url, config.timeout)
    except Exception as exc:
        logger.warning(f"Failed to access files for meeting {meeting.short_name}: {exc}")
        return collected

    # Get existing/invalid TDocs for filtering
    existing_ids = set()
    invalid_ids = set()
    if config.incremental:
        existing_ids = self.database.get_existing_tdoc_ids([meeting.working_group])
        invalid_ids = self.database.get_cached_invalid_tdocs()

    for filename in files:
        if not filename.endswith('.zip'):
            continue

        tdoc_id = filename.removesuffix('.zip').upper()

        # Check TDoc pattern
        if not TDOC_PATTERN.match(tdoc_id):
            continue

        # Skip if already processed (unless force_revalidate)
        if config.incremental and not config.force_revalidate:
            if tdoc_id in existing_ids or tdoc_id in invalid_ids:
                continue

        # Validate via portal
        portal_metadata = fetch_tdoc_metadata(tdoc_id, config.credentials, config.timeout)

        if portal_metadata is None:
            # Cache negative result
            self.database.cache_invalid_tdoc(tdoc_id)
            logger.debug(f"TDoc {tdoc_id} failed portal validation")
            continue

        # Build metadata object
        tdoc = TDocMetadata(
            tdoc_id=tdoc_id,
            url=f"{meeting.files_url}/{filename}",
            working_group=meeting.working_group,
            subgroup=meeting.subgroup,
            meeting=meeting.short_name,
            meeting_id=meeting.meeting_id,
            validated=True,
            validation_failed=False,
            **portal_metadata  # title, contact, etc.
        )

        collected.append(tdoc)

    return collected


def _list_files_at_url(self, url: str, timeout: int) -> list[str]:
    """List files at FTP or HTTP URL."""

    if url.startswith('ftp://'):
        return self._list_ftp_directory(url, timeout)
    elif url.startswith('http://') or url.startswith('https://'):
        return self._list_http_directory(url, timeout)
    else:
        raise ValueError(f"Unsupported URL scheme: {url}")


def _list_ftp_directory(self, url: str, timeout: int) -> list[str]:
    """Parse FTP directory listing for filenames.

    FTP LIST format: '09-22-25  10:31AM       <DIR>          TSG_RAN'
    Tokens: [date, time, size_or_dir, filename...]
    """
    from ftplib import FTP
    from urllib.parse import urlparse

    parsed = urlparse(url)
    ftp = FTP(parsed.hostname, timeout=timeout)
    ftp.login()
    ftp.cwd(parsed.path)

    entries = []
    ftp.retrlines('LIST', entries.append)
    ftp.quit()

    files = []
    for entry in entries:
        tokens = entry.split()
        if len(tokens) < 4:
            continue

        # Skip directories
        if '<DIR>' in entry.upper() or entry.startswith('d'):
            continue

        # Filename is everything from token[3] onward
        filename = ' '.join(tokens[3:])
        files.append(filename)

    return files


def _list_http_directory(self, url: str, timeout: int) -> list[str]:
    """Parse HTTP directory listing (Apache style)."""
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')

    # Apache directory listings use <a> tags
    files = []
    for link in soup.find_all('a'):
        href = link.get('href', '')
        if href and not href.startswith('?') and not href.startswith('/'):
            files.append(href)

    return files
```

### 5. CLI Updates (`src/tdoc_crawler/cli.py`)

**TODO:** Update `crawl` command:

```python
@app.command()
def crawl(
    cache_dir: Path = typer.Option(...),
    working_group: list[str] | None = typer.Option(None, "-w", "--working-group"),
    subgroup: list[str] | None = typer.Option(None, "-s", "--sub-group"),
    meeting_ids: list[int] | None = typer.Option(None, "--meeting-ids"),
    start_date: str | None = typer.Option(None, "--start-date"),
    end_date: str | None = typer.Option(None, "--end-date"),
    incremental: bool = typer.Option(True, "--incremental/--full"),
    force_revalidate: bool = typer.Option(False, "--force-revalidate"),
    workers: int = typer.Option(4, "--workers"),
    limit_tdocs: int | None = typer.Option(None, "--limit-tdocs"),
    max_retries: int = typer.Option(3, "--max-retries"),
    timeout: int = typer.Option(30, "--timeout"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    eol_username: str | None = typer.Option(None, "--eol-username"),
    eol_password: str | None = typer.Option(None, "--eol-password"),
) -> None:
    """Crawl TDocs from meetings (requires crawl-meetings first)."""

    # Parse dates
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    # Build config
    config = TDocCrawlConfig(
        cache_dir=cache_dir,
        working_groups=_parse_working_groups(working_group),
        subgroups=_parse_subgroups(subgroup),
        meeting_ids=meeting_ids,
        start_date=start,
        end_date=end,
        incremental=incremental,
        force_revalidate=force_revalidate,
        workers=workers,
        limits=_build_limits(limit_tdocs, None, None, None),
        credentials=_resolve_credentials(eol_username, eol_password, True),
        max_retries=max_retries,
        timeout=timeout,
        verbose=verbose,
    )

    # Execute crawl
    with TDocDatabase(database_path) as database:
        crawler = TDocCrawler(database)
        try:
            result = crawler.crawl(config)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            console.print("[yellow]Run 'crawl-meetings' first to populate meeting metadata[/yellow]")
            raise typer.Exit(code=1)

    # Display results
    console.print(f"[green]Processed {result.processed} meetings[/green]")
    console.print(f"[green]Found {result.inserted} new TDocs, updated {result.updated}[/green]")
    if result.errors:
        console.print(f"[yellow]{len(result.errors)} errors encountered[/yellow]")
```

### 6. Database Migration

**TODO:** Create migration script to update schema:

```python
def migrate_tdocs_table_v2(database: TDocDatabase) -> None:
    """Add portal metadata columns to tdocs table."""

    with database._cursor() as cursor:
        # Add new columns (safe if already exist)
        columns_to_add = [
            ("title", "TEXT"),
            ("contact", "TEXT"),
            ("tdoc_type", "TEXT"),
            ("for_purpose", "TEXT"),
            ("agenda_item", "TEXT"),
            ("status", "TEXT"),
            ("is_revision_of", "TEXT"),
            ("validated", "BOOLEAN DEFAULT 0"),
            ("validation_failed", "BOOLEAN DEFAULT 0"),
        ]

        for col_name, col_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE tdocs ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                # Column already exists
                pass

        database._conn.commit()
```

### 7. Testing

**TODO:** Add comprehensive tests:

- `test_portal.py`: Portal parsing tests
- `test_crawler_refactored.py`: New crawler workflow tests
- `test_parallel_processing.py`: Concurrent crawling tests
- Update existing tests for new schema

## Implementation Order

1. ✅ Update models (TDocMetadata, TDocRecord, TDocCrawlConfig)
1. ⏳ Create `portal.py` module with parsing logic
1. ⏳ Update database schema and add helper methods
1. ⏳ Refactor `TDocCrawler` class
1. ⏳ Update CLI command
1. ⏳ Add migration script
1. ⏳ Write tests
1. ⏳ Update documentation

## Open Questions

1. **Portal authentication:** Need to test login flow with actual credentials
1. **HTML structure:** Need to parse actual portal page to confirm field locations
1. **Rate limiting:** Should we add delays between portal requests?
1. **Batch size:** For parallel workers, should we batch meetings or process all?

## Next Steps

1. Test portal access with credentials to understand HTML structure
1. Implement portal parsing module
1. Update database schema with migration
1. Refactor crawler class
1. Update CLI and tests
