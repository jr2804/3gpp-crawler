# Review and Improvements for AGENTS.md

**Date**: 2025-10-22
**Reviewer**: AI Assistant
**Purpose**: Comprehensive review of AGENTS.md coding instructions to ensure accurate code regeneration

---

## Executive Summary

The current AGENTS.md file requires significant updates to reflect recent architectural changes and implementation details. The document still references obsolete FTP-based patterns and lacks critical information about:

1. HTTP-based implementation with requests/BeautifulSoup
2. Subdirectory detection and crawling (Docs/)
3. Fuzzy meeting name matching patterns
4. Portal authentication module (portal.py)
5. Simplified TDoc pattern specification
6. Updated test mocking patterns

**Impact**: A coding assistant following current AGENTS.md would regenerate code with FTP instead of HTTP, miss subdirectory crawling, and lack fuzzy matching capabilities.

---

## Critical Issues (High Priority)

### 1. HTTP Implementation Not Documented

**Issue**: AGENTS.md section "Implementation Patterns > FTP Directory Filtering" still references FTP patterns and uses obsolete terminology.

**Current Text** (Line 491-502):
```markdown
### FTP Directory Filtering

Exclude non-meeting directories when crawling:

```python
# In crawlers/tdocs.py
EXCLUDED_DIRS = ["Inbox", "Outbox", "Archive", "Old"]
TDOC_PATTERN = re.compile(r"^[RSTC]\d+-\d+", re.IGNORECASE)
```

**Problems**:
- Title says "FTP Directory Filtering" but implementation is HTTP-based
- TDoc pattern shown is obsolete (should be `r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)"`)
- No mention of HTTP session management
- Missing BeautifulSoup HTML parsing patterns

**Proposed Fix**:
```markdown
### HTTP Directory Crawling and File Detection

**HTTP Session Management**:

```python
# In crawlers/tdocs.py
def _create_session(self, config: TDocCrawlConfig) -> requests.Session:
    """Create HTTP session with retry logic and timeout configuration."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=config.max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
```

**HTML Directory Parsing**:

```python
# Parse HTML directory listings
response = session.get(directory_url, timeout=config.timeout)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

# Extract file links
for link in soup.find_all("a"):
    href = link.get("href")
    if not href or not isinstance(href, str):
        continue

    # Check if it's a TDoc file
    match = TDOC_PATTERN.search(href)
    if match:
        tdoc_id = match.group(1).upper()
        # ... process TDoc
```

**TDoc Pattern** (Simplified):

```python
# TDoc filename pattern: [RSC][1-6P] followed by 4-10 chars, then extension
TDOC_PATTERN = re.compile(r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)", re.IGNORECASE)

# Directories to exclude from crawling
EXCLUDED_DIRS = {"Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report"}
EXCLUDED_DIRS_NORMALIZED = {entry.upper() for entry in EXCLUDED_DIRS}
```

**Pattern Explanation**:
- First character: `[RSC]` - Working group (R=RAN, S=SA, C=CT)
- Second character: `[1-6P]` - Subgroup (1-6) or Plenary (P)
- Following: `.{4,10}` - 4 to 10 characters (any valid filename characters)
- Extension: `\.(zip|txt|pdf)` - Must end with .zip, .txt, or .pdf
- Case-insensitive via `re.IGNORECASE` flag
```

---

### 2. Subdirectory Detection Missing

**Issue**: AGENTS.md does not document subdirectory detection and crawling, which is critical for finding TDocs.

**Current State**: No mention of subdirectory patterns or the fact that TDocs are typically in "Docs/" subdirectories.

**Proposed Addition** (New section after "HTTP Directory Crawling"):

```markdown
### Subdirectory Detection and Crawling

**Problem**: TDocs are typically stored in subdirectories like "Docs/", not in the base meeting directory.

**Solution**: Detect and crawl TDoc-specific subdirectories:

```python
# In crawlers/tdocs.py

# Subdirectories that may contain TDocs (case-insensitive matching)
TDOC_SUBDIRS = {"Docs", "Documents", "Tdocs", "TDocs", "DOCS"}
TDOC_SUBDIRS_NORMALIZED = {entry.upper() for entry in TDOC_SUBDIRS}

def _crawl_meeting(
    self,
    session: requests.Session,
    meeting,  # MeetingMetadata
    config: TDocCrawlConfig,
    collected: list[TDocMetadata],
    seen_ids: set[str],
    existing_ids: set[str],
    targets: set[str] | None,
) -> None:
    """Crawl a specific meeting's HTTP directory for TDocs.

    This method first scans the base meeting directory for TDoc subdirectories
    (like "Docs/") and crawls those. If no subdirectories are found, it scans
    the base directory directly.
    """
    base_url = meeting.files_url
    if not base_url.endswith("/"):
        base_url += "/"

    # Fetch base directory listing
    response = session.get(base_url, timeout=config.timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Look for TDoc subdirectories (e.g., "Docs/")
    subdirs_found = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if not href or not isinstance(href, str):
            continue

        # Skip query strings and parent directory links
        if href.startswith(("?", "..")):
            continue

        # Extract directory name from href
        dir_name = href.rstrip("/").split("/")[-1]

        # Check if this is a TDoc subdirectory
        if dir_name.upper() in TDOC_SUBDIRS_NORMALIZED:
            # Build full URL
            if href.startswith("http"):
                subdir_url = href if href.endswith("/") else href + "/"
            else:
                subdir_url = base_url + href.lstrip("/")
                if not subdir_url.endswith("/"):
                    subdir_url += "/"
            subdirs_found.append(subdir_url)

    # Crawl subdirectories if found, otherwise crawl base directory
    if subdirs_found:
        for subdir_url in subdirs_found:
            self._scan_directory_for_tdocs(session, subdir_url, meeting, ...)
    else:
        self._scan_directory_for_tdocs(session, base_url, meeting, ...)
```

**Key Points**:
- Always check for subdirectories first
- Handle both full URLs and relative paths
- Ensure all URLs end with "/"
- Fall back to base directory if no subdirectories found
```

---

### 3. Fuzzy Meeting Name Matching Not Documented

**Issue**: AGENTS.md does not document the fuzzy matching algorithm for resolving meeting names from portal to database.

**Current State**: No mention of meeting name variations or resolution strategy.

**Proposed Addition** (New section in "Implementation Patterns"):

```markdown
### Fuzzy Meeting Name Matching

**Problem**: Meeting names from the portal (e.g., "SA4#133-e") don't always match database format (e.g., "S4-133-e" or "3GPPSA4-e (AH) Audio SWG post 130").

**Solution**: Multi-stage fuzzy matching with SQL optimization:

```python
# In cli.py

def _normalize_portal_meeting_name(portal_meeting: str) -> str:
    """Normalize portal meeting name to database format.

    Examples:
        "SA4#133-e" → "S4-133-e"
        "RAN1#98" → "R1-98"
    """
    # Replace "#" with "-"
    normalized = portal_meeting.replace("#", "-")

    # Handle full working group names (SA, RAN, CT)
    for full_name, short_prefix in [("SA", "S"), ("RAN", "R"), ("CT", "C")]:
        if normalized.startswith(f"{full_name}"):
            # Extract the subgroup number if present
            for i, char in enumerate(normalized[len(full_name):]):
                if not char.isdigit():
                    break
            else:
                i += 1
            if i > 0:
                subgroup_num = normalized[len(full_name):len(full_name) + i]
                rest = normalized[len(full_name) + i:]
                normalized = f"{short_prefix}{subgroup_num}{rest}"
                break

    return normalized

def _resolve_meeting_id(database: TDocDatabase, meeting_name: str) -> int | None:
    """Resolve meeting name to meeting_id using fuzzy matching.

    Strategy (in order):
    1. Exact match (case-insensitive)
    2. Normalized name match
    3. SQL LIKE patterns for prefix/suffix matching
    4. Full table scan for reverse prefix/suffix matching

    Args:
        database: Database connection
        meeting_name: Meeting identifier from portal

    Returns:
        Meeting ID if found, None otherwise
    """
    # 1. Try exact match (case-insensitive)
    cursor = database.connection.execute(
        "SELECT meeting_id FROM meetings WHERE short_name = ? COLLATE NOCASE",
        (meeting_name,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # 2. Try normalized name
    normalized = _normalize_portal_meeting_name(meeting_name)
    if normalized != meeting_name:
        cursor = database.connection.execute(
            "SELECT meeting_id FROM meetings WHERE short_name = ? COLLATE NOCASE",
            (normalized,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # 3. SQL LIKE patterns (use database indexes)
    candidate_lower = meeting_name.lower()
    normalized_lower = normalized.lower()

    for pattern in [
        f"{candidate_lower}%",  # candidate is prefix of cached
        f"%{candidate_lower}",  # candidate is suffix of cached
    ]:
        cursor = database.connection.execute(
            "SELECT meeting_id FROM meetings WHERE LOWER(short_name) LIKE ? LIMIT 1",
            (pattern,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # Try with normalized candidate
    if normalized_lower != candidate_lower:
        for pattern in [
            f"{normalized_lower}%",
            f"%{normalized_lower}",
        ]:
            cursor = database.connection.execute(
                "SELECT meeting_id FROM meetings WHERE LOWER(short_name) LIKE ? LIMIT 1",
                (pattern,),
            )
            row = cursor.fetchone()
            if row:
                return row[0]

    # 4. Reverse patterns: cached is prefix/suffix of candidate (full scan)
    cursor = database.connection.execute("SELECT meeting_id, short_name FROM meetings")
    for meeting_id, cached_name in cursor.fetchall():
        cached_lower = cached_name.lower()
        if candidate_lower.startswith(cached_lower) or candidate_lower.endswith(cached_lower):
            return meeting_id
        if normalized_lower != candidate_lower:
            if normalized_lower.startswith(cached_lower) or normalized_lower.endswith(cached_lower):
                return meeting_id

    return None
```

**Important**: Do NOT use substring matching (e.g., `%candidate%`) as it matches fragments and causes false positives. Only use prefix/suffix matching.
```

---

### 4. Portal Authentication Module Missing

**Issue**: AGENTS.md project structure section does not list `crawlers/portal.py`, which is a critical module.

**Current Structure** (Lines 181-193):
```markdown
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
```

**Proposed Fix**:
```markdown
src/tdoc_crawler/
├── models/              # Data models and configuration
│   ├── __init__.py      # Re-exports all public symbols for backward compatibility
│   ├── base.py          # BaseConfigModel, utilities, enums, PortalCredentials
│   ├── working_groups.py  # WorkingGroup enum with tbid/ftp_root properties
│   ├── subworking_groups.py  # SubworkingGroup model
│   ├── crawl_limits.py  # CrawlLimits configuration
│   ├── tdocs.py         # TDocMetadata, TDocRecord, TDocCrawlConfig, QueryConfig
│   └── meetings.py      # MeetingMetadata, MeetingRecord, MeetingCrawlConfig
├── crawlers/            # Web scraping and HTTP crawling logic
│   ├── __init__.py      # Re-exports all public symbols (includes TDOC_PATTERN, EXCLUDED_DIRS, TDOC_SUBDIRS)
│   ├── tdocs.py         # TDocCrawler - HTTP directory traversal, TDoc discovery, subdirectory detection
│   ├── meetings.py      # MeetingCrawler - HTML parsing, date extraction
│   └── portal.py        # PortalSession - 3GPP portal authentication, TDoc metadata fetching
├── database.py          # SQLite persistence layer with typed wrappers
├── cli.py               # Typer-based CLI with 6 commands, fuzzy matching helpers
├── __init__.py          # Package initialization
└── __main__.py          # Entry point for `python -m tdoc_crawler`
```

**New Section to Add** (After "Module Design Principles"):

```markdown
### Portal Authentication Module

The `crawlers/portal.py` module handles 3GPP portal authentication and TDoc metadata fetching:

**Key Components**:

```python
# Portal session with authentication
class PortalSession:
    """Manages authenticated session with 3GPP portal."""

    def __init__(self, credentials: PortalCredentials, timeout: int = 30) -> None:
        """Initialize portal session with EOL credentials."""
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()
        self._authenticated = False

    def authenticate(self) -> None:
        """Authenticate with 3GPP portal using JavaScript-based AJAX login."""
        # Visit login page to establish session
        # Call AJAX endpoint LoginEOL.ashx with credentials
        # Parse JSON response for authentication result

    def get_tdoc_metadata(self, tdoc_id: str) -> dict[str, str]:
        """Fetch TDoc metadata from portal page.

        URL: https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid={tdoc_id}
        """
        # Ensure authenticated
        # Fetch portal page
        # Parse HTML with BeautifulSoup
        # Extract metadata fields

# Public functions
def fetch_tdoc_metadata(
    tdoc_id: str,
    credentials: PortalCredentials,
    timeout: int = 30,
) -> dict[str, str]:
    """Fetch TDoc metadata with automatic authentication."""
    with PortalSession(credentials, timeout) as session:
        session.authenticate()
        return session.get_tdoc_metadata(tdoc_id)

# Exceptions
class PortalAuthenticationError(Exception):
    """Raised when portal authentication fails."""

class PortalParsingError(Exception):
    """Raised when portal page parsing fails."""
```

**Usage Pattern**:

```python
from tdoc_crawler.crawlers import fetch_tdoc_metadata
from tdoc_crawler.models import PortalCredentials

credentials = PortalCredentials(username="user", password="pass")
metadata = fetch_tdoc_metadata("R1-2301234", credentials)
# Returns: {"title": "...", "meeting": "...", "contact": "...", ...}
```
```

---

### 5. Test Patterns Outdated

**Issue**: AGENTS.md section "Testing > Mock Patterns > Mocking FTP Connections" references FTP mocking, which is obsolete.

**Current Text** (Lines 923-963):
```markdown
#### Mocking FTP Connections

**CRITICAL**: After module refactoring, FTP must be patched at `tdoc_crawler.crawlers.tdocs.FTP` (NOT `tdoc_crawler.crawler.FTP`)

```python
from unittest.mock import MagicMock, patch

@patch("tdoc_crawler.crawlers.tdocs.FTP")
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
```

**Proposed Replacement**:

```markdown
#### Mocking HTTP Requests

**CRITICAL**: Mock `requests.Session` at `tdoc_crawler.crawlers.tdocs.requests.Session`

```python
from unittest.mock import MagicMock, patch

@patch("tdoc_crawler.crawlers.tdocs.requests.Session")
def test_crawl_collects_tdocs(
    mock_session_class: MagicMock,
    test_db_path: Path,
) -> None:
    """Test HTTP crawling with mocked connection."""
    from tdoc_crawler.models import MeetingMetadata

    # Mock HTML directory listing
    html_content = """
    <html><body>
    <a href="R1-2301234.zip">R1-2301234.zip</a> 2048 bytes
    </body></html>
    """

    # Setup mock session
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = html_content
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response
    mock_session.close.return_value = None
    mock_session_class.return_value = mock_session

    # Setup database with meeting
    with TDocDatabase(test_db_path) as database:
        meeting = MeetingMetadata(
            meeting_id=12345,
            tbid=373,  # RAN
            subtb=379,  # RAN1
            working_group=WorkingGroup.RAN,
            subgroup="R1",
            short_name="RAN1#98",
            files_url="https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/",
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 19),
            location="Athens, Greece",
        )
        database.upsert_meeting(meeting)

        # Run crawler
        crawler = TDocCrawler(database)
        config = TDocCrawlConfig(
            cache_dir=test_db_path.parent,
            working_groups=[WorkingGroup.RAN],
            incremental=False,
        )
        result = crawler.crawl(config)

    assert result.processed == 1
    assert result.inserted == 1
```

**Key Differences from FTP Mocking**:
- Mock `requests.Session` not `FTP`
- Mock `session.get()` to return HTML content
- Use BeautifulSoup-parseable HTML in mock responses
- Meeting metadata must include `files_url` (HTTP URL)
- No need to mock `retrlines()` or FTP LIST format
```

---

## Medium Priority Issues

### 6. TDoc Pattern Documentation Inconsistent

**Issue**: Multiple sections show different or incomplete TDoc patterns.

**Occurrences**:
1. Line 90: Describes old format "at least additional 4 arbitrary characters"
2. Line 491: Shows obsolete pattern `r"^[RSTC]\d+-\d+"`
3. Missing simplified pattern explanation

**Proposed Fix**:

Update Line 90-92 from:
```markdown
- The first letter of the TDoc number indicates the working group, e.g., `R` for RAN, `S` for SA, and `C` for CT. The second letter indicates the sub-working group or plenary, e.g., `1` for RAN1, `4` for SA4, and `P` for plenary. All other characters in the TDoc number can vary, but at least additional 4 arbitrary characters are required.
```

To:
```markdown
- The TDoc number follows this format: `[RSC][1-6P].{4,10}\.(zip|txt|pdf)`
  - First character: Working group (`R` for RAN, `S` for SA, `C` for CT)
  - Second character: Subgroup (`1`-`6`) or Plenary (`P`)
  - Following 4-10 characters: Can be digits, letters, dashes, etc.
  - File extension: Must be `.zip`, `.txt`, or `.pdf`
  - Examples: `R1-2301234.zip`, `S4aA220001.zip`, `CP-123456.zip`
```

Add new section after line 92:
```markdown
### TDoc Filename Pattern Details

The TDoc crawler uses this simplified regex pattern:

```python
TDOC_PATTERN = re.compile(r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)", re.IGNORECASE)
```

**Pattern Breakdown**:
- `[RSC]` - Working group: R (RAN), S (SA), C (CT)
- `[1-6P]` - Subgroup (1-6) or Plenary (P)
- `.{4,10}` - 4 to 10 characters (any valid filename characters)
- `\.(zip|txt|pdf)` - Required file extension
- `re.IGNORECASE` - Case-insensitive matching

**Examples that Match**:
- Standard format: `R1-2301234.zip`, `S4-251209.txt`, `C1-2312345.pdf`
- Plenary format: `RP-230045.txt`, `SP-240001.zip`, `CP-123456.zip`
- Ad-hoc format: `S4aA220001.zip`, `R1eE230045.txt`
- Case variations: `r1-2301234.ZIP`, `S4-251209.TXT`

**Examples that Don't Match**:
- Wrong working group: `T1-2300456.zip` (T is invalid, use C for CT)
- Wrong subgroup: `R7-123456.zip` (subgroup must be 1-6 or P)
- Too short: `R1-12.zip` (only 2 chars after R1, need 4-10)
- Too long: `R1-12345678901.zip` (11 chars, exceeds maximum of 10)
- Wrong extension: `R1-2301234.doc` (must be .zip, .txt, or .pdf)
- Not a TDoc: `README.txt`, `data.csv`
```

---

### 7. Crawl Command Description Incomplete

**Issue**: Section "Crawling TDocs from Meetings" (Line 249-292) doesn't mention subdirectory detection or fuzzy matching.

**Proposed Addition** (Insert before "Portal Metadata Fields:"):

```markdown
**Subdirectory Detection**:

The crawler automatically detects and crawls TDoc-specific subdirectories:

1. **Fetch base meeting directory** from `files_url`
2. **Parse HTML** to extract directory links
3. **Check for TDoc subdirectories** (Docs/, Documents/, etc.)
4. **If subdirectories found**: Crawl each subdirectory
5. **If no subdirectories**: Crawl base directory directly

**Meeting Name Resolution**:

When validating TDocs via the portal, the returned meeting name may not match the database format:

- Portal returns: "SA4#133-e" or "SA4-e (AH) Audio SWG post 130"
- Database stores: "S4-133-e" or "3GPPSA4-e (AH) Audio SWG post 130"

The crawler uses fuzzy matching to resolve meeting names:

1. **Exact match** (case-insensitive)
2. **Normalized match** (SA4#133-e → S4-133-e)
3. **Prefix/suffix matching** (handles "3GPPSA4..." vs "SA4...")
4. **SQL optimization** (uses LIKE queries before full table scans)

See "Implementation Patterns > Fuzzy Meeting Name Matching" for detailed implementation.
```

---

### 8. CLI Helper Functions Not Fully Documented

**Issue**: Section "CLI Commands Implementation > Common Patterns" (Lines 436-447) lists helper functions but doesn't document their implementations.

**Proposed Addition** (After "Credential Handling:"):

```markdown
**Helper Function Implementations**:

```python
# In cli.py

def resolve_cache_dir(cache_dir: Path | None) -> Path:
    """Resolve cache directory from CLI parameter, environment, or default."""
    if cache_dir:
        return cache_dir
    env_cache = os.getenv("TDOC_CACHE_DIR")
    if env_cache:
        return Path(env_cache)
    return Path.cwd() / "cache"

def resolve_db_file(cache_dir: Path, db_file: Path | None) -> Path:
    """Resolve database file path."""
    if db_file:
        return db_file
    env_db = os.getenv("TDOC_DB_FILE")
    if env_db:
        return Path(env_db)
    return cache_dir / "tdoc_crawler.db"

def get_credentials(
    eol_username: str | None,
    eol_password: str | None,
    prompt_if_missing: bool = True,
) -> PortalCredentials | None:
    """Get credentials from CLI, environment, or interactive prompt."""
    username = eol_username or os.getenv("EOL_USERNAME")
    password = eol_password or os.getenv("EOL_PASSWORD")

    if username and password:
        return PortalCredentials(username=username, password=password)

    if prompt_if_missing:
        username = typer.prompt("EOL username")
        password = typer.prompt("EOL password", hide_input=True)
        return PortalCredentials(username=username, password=password)

    return None

def _infer_working_groups_from_ids(tdoc_ids: list[str]) -> list[WorkingGroup]:
    """Infer working groups from TDoc IDs for targeted fetching."""
    mapping = {
        "R": WorkingGroup.RAN,
        "S": WorkingGroup.SA,
        "C": WorkingGroup.CT,
        "T": WorkingGroup.CT,  # Support T as alias for CT (legacy)
    }
    groups: list[WorkingGroup] = []
    for tdoc_id in tdoc_ids:
        if not tdoc_id:
            continue
        first_char = tdoc_id[0].upper()
        group = mapping.get(first_char)
        if group and group not in groups:
            groups.append(group)
    # Default to all groups if none inferred
    return groups or [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]
```
```

---

## Low Priority Issues (Documentation Clarity)

### 9. File Size Guidelines Unclear

**Issue**: Line 203 says "CLI file: 600+ lines (acceptable due to command definitions)" but actual CLI is 864 lines.

**Proposed Fix**:
```markdown
When splitting modules:
- Base utilities: 20-70 lines
- Model files: 80-150 lines
- Crawler files: 150-350 lines
- CLI file: 600-900 lines (acceptable due to command definitions and helper functions)
- Database file: 900-1100 lines (acceptable due to schema + queries)
```

---

### 10. Documentation Workflow Example Outdated

**Issue**: Line 1025 example references wrong project name:

**Current**:
```markdown
1. Implement: tracktor_tools/cli.py - add new command
2. Test: tests/test_activities.py - add tests
```

**Proposed Fix**:
```markdown
1. Implement: src/tdoc_crawler/cli.py - add new command
2. Test: tests/test_cli.py - add tests
3. Document in history: docs/history/2025-01-15_SUMMARY_01_NEW_VALIDATE_COMMAND.md
4. Update main reference: docs/QUICK_REFERENCE.md - add command documentation
5. Verify: README.md contains link to QUICK_REFERENCE.md
```

---

## Structural Improvements

### 11. Add Architecture Decision Section

**Proposed New Section** (Insert after "Project Structure"):

```markdown
## Architectural Decisions

### HTTP-Based Crawling (Not FTP)

**Decision**: Use HTTP with requests/BeautifulSoup instead of FTP.

**Rationale**:
- Server is HTTP-accessible (no FTP needed)
- HTTP provides better error handling (status codes vs FTP errors)
- Easier to test (simple HTTP mocking vs FTP protocol simulation)
- Built-in retry logic via urllib3
- Connection pooling for better performance

**Implementation**: See `crawlers/tdocs.py` and section "HTTP Directory Crawling".

---

### Meeting-Based Crawling (Not Tree Walking)

**Decision**: Query meetings from database first, then crawl their specific directories.

**Rationale**:
- Faster: Direct directory access vs recursive tree walking
- Efficient filtering: Database queries vs post-processing
- Meeting linkage: Proper foreign key relationships
- Incremental updates: Track last_crawled per meeting

**Implementation**:
1. `crawl-meetings` populates meetings database with `files_url`
2. `crawl` queries meetings matching filters
3. For each meeting, crawl `files_url` directory (with subdirectory detection)
4. Establish `meeting_id` foreign key in TDocMetadata

---

### Subdirectory Detection (Docs/)

**Decision**: Automatically detect and crawl TDoc-specific subdirectories.

**Rationale**:
- TDocs typically in "Docs/" subdirectory, not base directory
- Avoids crawling irrelevant files (agendas, reports)
- Handles variations (Docs, Documents, DOCS, etc.)

**Implementation**: See section "Subdirectory Detection and Crawling".

---

### Fuzzy Meeting Name Matching

**Decision**: Multi-stage fuzzy matching for meeting name resolution.

**Rationale**:
- Portal and database use different formats ("SA4#133" vs "S4-133")
- Meeting names have prefixes/variations ("SA4..." vs "3GPPSA4...")
- Need robust matching without false positives

**Implementation**: See section "Fuzzy Meeting Name Matching".

---

### Simplified TDoc Pattern

**Decision**: Use `[RSC][1-6P].{4,10}\.(zip|txt|pdf)` regex pattern.

**Rationale**:
- Clear specification: WG + subgroup + variable chars + extension
- Matches standard, ad-hoc, and plenary formats
- Simple to understand and maintain
- Avoids complex alternations

**Implementation**: See section "TDoc Filename Pattern Details".
```

---

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)
1. Replace FTP patterns with HTTP implementation
2. Add subdirectory detection documentation
3. Document portal.py module
4. Update test mocking patterns
5. Fix TDoc pattern documentation

### Phase 2: Medium Priority (Next)
6. Add fuzzy matching documentation
7. Document CLI helper functions
8. Complete crawl command description
9. Update file size guidelines

### Phase 3: Low Priority (As Needed)
10. Fix documentation workflow example
11. Add architectural decisions section

---

## Testing Recommendations

After updating AGENTS.md:

1. **Regeneration Test**: Ask a fresh AI assistant to implement the TDoc crawler from scratch using only AGENTS.md
2. **Verification Points**:
   - Uses HTTP (not FTP)
   - Implements subdirectory detection
   - Includes fuzzy matching
   - Has portal.py module
   - Uses correct TDoc pattern
   - Implements HTTP mocking in tests
3. **Gap Analysis**: Compare regenerated code with actual codebase to identify remaining gaps

---

## Conclusion

The AGENTS.md file requires substantial updates to reflect the current HTTP-based, meeting-driven architecture. The most critical issues are:

1. ❌ **FTP references** throughout (should be HTTP)
2. ❌ **Missing subdirectory detection** (critical feature)
3. ❌ **Missing fuzzy matching** (critical for query command)
4. ❌ **Missing portal.py** (entire module undocumented)
5. ❌ **Obsolete test patterns** (FTP mocking vs HTTP mocking)

**Estimated Impact**: Without these updates, a coding assistant would regenerate code that:
- Uses FTP instead of HTTP (architectural mismatch)
- Processes 0 TDocs (missing subdirectory detection)
- Fails queries with meeting name mismatches (no fuzzy matching)
- Lacks portal authentication (can't validate TDocs)

**Recommendation**: Prioritize Phase 1 critical fixes before any further development.

---

**Review completed**: 2025-10-22
**Total issues identified**: 11
**Critical issues**: 5
**Medium priority**: 3
**Low priority**: 3
