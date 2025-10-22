# Assistant Rules for TDoc-Crawler - Command line tool for querying structured 3GPP TDoc data

---
description: General Guidelines
alwaysApply: true
---

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

## General Coding Guidelines

### Instructions

**Your fundamental responsibility:** Remember you are a senior engineer and have a serious responsibility to be clear, factual, think step by step and be systematic, express expert opinion, and make use of the user's attention wisely.

**Rules must be followed:** It is your responsibility to carefully read these rules as well as Python or other language-specific rules included here.

Therefore:

- Be concise. State answers or responses directly, without extra commentary. Or (if it is clear) directly do what is asked.

- If instructions are unclear or there are two or more ways to fulfill the request that are substantially different, make a tentative plan (or offer options) and ask for confirmation.

- If you can think of a much better approach that the user requests, be sure to mention it. It's your responsibility to suggest approaches that lead to better, simpler solutions.

- Give thoughtful opinions on better/worse approaches, but NEVER say "great idea!" or "good job" or other compliments, encouragement, or non-essential banter. Your job is to give expert opinions and to solve problems, not to motivate the user.

- Avoid gratuitous enthusiasm or generalizations. Use thoughtful comparisons like saying which code is "cleaner" but don't congratulate yourself. Avoid subjective descriptions. For example, don't say "I've meticulously improved the code and it is in great shape!" That is useless generalization. Instead, specifically say what you've done, e.g., "I've added types, including generics, to all the methods in `Foo` and fixed all linter errors."

- Use `git` for version control. Use `main` as the main branch name.
- Use `git add ...` to add new files, **but only rarely** and **only those that are very likely** to be committed. **Do not add files** that are most likely to be deleted or changed significantly in the following steps. In doubt, do not add the file and ask/confirm with the user.
- **Never** run `git commit` or `git push` on your own!
- `.env` files **MUST NOT** be committed to version control.

### Using Comments

- Keep all comments concise and clear and suitable for inclusion in final production.

- DO use comments whenever the intent of a given piece of code is subtle or confusing or avoids a bug or is not obvious from the code itself.

- DO NOT repeat in comments what is obvious from the names of functions or variables or types.

- DO NOT include comments that reflect what you did, such as "Added this function" as this is meaningless to anyone reading the code later. (Instead, describe in your message to the user any other contextual information.)

- DO NOT use fancy or needlessly decorated headings like "===== MIGRATION TOOLS =====" in comments.

- DO NOT number steps in comments. These are hard to maintain if the code changes. NEVER DO THIS: "// Step 3: Fetch the data from the cache". This is fine: "// Now fetch the data from the cache"

- DO NOT use emojis or special unicode characters like ① or • or – or — in comments.

- Use emojis in output if it enhances the clarity and can be done consistently. You may use ✔︎ and ✘ to indicate success and failure, and ∆ and ‼︎ for user-facing warnings and errors, for example, but be sure to do it consistently. DO NOT use emojis gratuitously in comments or output. You may use then ONLY when they have clear meanings (like success or failure). Unless the user says otherwise, avoid emojis and Unicode in comments as clutters the output with little benefit.

## Background on 3GPP, TDocs and Meetings

### General

3GPP (3rd Generation Partnership Project) is a collaboration between groups of telecommunications standards associations, known as the Organizational Partners. 3GPP develops protocols for mobile telecommunications. See also `https://www.3gpp.org/`.

Since 3GPP is not a legal entity, technical administration and infrastructure is provided by the European Telecommunications Standards Institute (ETSI). For this reason, several 3GPP resources like e.g., the meeting information and registration page (`https://portal.etsi.org/Meetings.aspx#/`).

To access certain resources, you need to have an ETSI Online Account (EOL). However, the files on the 3GPP FTP server are publicly accessible to everyone, but for parsing metadata, login to certain webpages may be required.

### What are TDocs?

TDocs (Temporary Documents) are meeting documents produced by members participating in 3GPP working (WG) and sub-working (SWG) groups. They include proposals, reports, and other documents related to the development of 3GPP standards.

### Where to find and how to locate TDocs?

TDocs are stored on the 3GPP web server and are publicly accessible to everyone. They are available at the following base URL: `https://www.3gpp.org/ftp/tsg_<working_group_identifier>/<sub-working_group_identifier>/<meeting_identifier>/Docs/<tdoc_nbr>.zip` (sometimes, in very rare cases, the file extension `.pdf` may be used). The server has a FTP-like structure, but is completely accessible via HTTP(S). There is no need to use FTP protocol to access the files. Thus, the term "FTP server" is used for historical reasons only and is used synonymously for the HTTP-based file server.

Note that ...

- `<tdoc_nbr>` is the filename stem of the TDoc file, e.g., `R1-2301234`.
- The TDoc number follows this format: `[RSC][1-6P].{4,10}\.(zip|txt|pdf)`
  - First character: Working group (`R` for RAN, `S` for SA, `C` for CT)
  - Second character: Subgroup (`1`-`6`) or Plenary (`P`)
  - Following 4-10 characters: Can be digits, letters, dashes, etc.
  - File extension: Must be `.zip`, `.txt`, or `.pdf`
  - Examples: `R1-2301234.zip`, `S4aA220001.zip`, `CP-123456.zip`
- More than 99% of TDocs are in `.zip` format, with only a few rare cases of `.pdf` or `.txt` files.
- Otherwise, there is no specific format for or limit of the number of digits, letters, dashes, etc.
- Any other files on the server that do not follow this naming convention are not TDocs and should be ignored.
- `<sub-working_group_identifier>` and `<meeting_identifier>` are just path names and do not have a fixed format or naming convention, they also do not correspond to the official SWG and meeting identifiers (i.e., they are arbitrary path names on the server and thus do not need to be stored in the database).
- Each WG has multiple SWGs (sub-groups, simply numbered from 1 to n) as well as a so-called "plenary" group, which is not a SWG but just called "plenary". The plenary group usually has the identifier `TSG_<WG>`, e.g., `TSG_RAN` for RAN plenary TDocs.

There are three main working groups in 3GPP that handle TDocs:

**RAN** (Radio Access Network):

- Focuses on the radio aspects of mobile communications, including the development of standards for radio access technologies like LTE and 5G NR.
- Their `working_group_identifier` is `ran`, thus the base URL for RAN TDocs is `https://www.3gpp.org/ftp/tsg_ran/`.
- Their technical body id (tbid) is `373`. Their plenary meeting is considered as a sub-working group (SWG), with their id (SubTB) also being `373`.
- Their other SWGs are RAN1, RAN2, RAN3, RAN4, RAN5, and RAN6 with corresponding tbids `379`, `380`, `381`, `382`, `657`, `843`.

**SA** (Service and System Aspects):

- Deals with the overall architecture and service aspects of mobile networks, including core network functionalities and service requirements.
- Their `working_group_identifier` is `sa`, thus the base URL for SA TDocs is `https://www.3gpp.org/ftp/tsg_sa/`.
- Their technical body id (tbid) is `375`. Their plenary meeting is considered as a sub-working group (SWG), with their id (SubTB) also being `375`.
- Their other SWGs are SA1, SA2, SA3, SA4, SA5, and SA6 with corresponding tbids `384`, `385`, `386`, `387`, `388`, `825`.

**CT** (Core Network and Terminals):

- Concentrates on the core network and terminal aspects, including protocols and interfaces between the core network and user equipment.
- Their `working_group_identifier` is `ct`, thus the base URL for CT TDocs is `https://www.3gpp.org/ftp/tsg_ct/`.
- Their technical body id (tbid) is `649`. Their plenary meeting is considered as a sub-working group (SWG), with their id (SubTB) also being `649`.
- Their other SWGs are CT1, CT2, CT3, CT4, CT5, and CT6 with corresponding tbids `651`, `652`, `653`, `654`, `655`, `656`.

### TDoc direct links

When the TDoc number is known, this ASPX link to the 3GPP portal can be used to query some metadata: `
`https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=<tdoc_nbr>`, where `<tdoc_nbr>` is the TDoc number, e.g., `R1-2301234`.

### Meetings

Any TDoc is always allocated to a specific 3GPP meeting. Meetings are organized by working groups and have unique meeting identifiers (strings like e.g., `SA4#134` or `SA4-(AH) Audio SWG post 132`). The naming convention is quite inconsistent and was changed over the years, so they are **not** useful to parse any information from them directly. In addition, each meeting also has a unique integer number, which could be used as a key in the cache database.

Meeting information, including dates and locations, can be found on the 3GPP portal via a dynamically generated pages at
`https://www.3gpp.org/dynareport?code=Meetings-<ID>.htm`, where `<ID>` is an unique two-digitworking group identifier as shown in this table (URL and ID are case-sensitive!):

| ID | Title       | tbid | SubTB |
|----|-------------|------|-------|
| SP | SA Plenary  | 375  | 375   |
| S1 | SA1         | 375  | 384   |
| S2 | SA2         | 375  | 385   |
| S3 | SA3         | 375  | 386   |
| S4 | SA4         | 375  | 387   |
| S5 | SA5         | 375  | 388   |
| S6 | SA6         | 375  | 825   |
| CP | CT Plenary  | 649  | 649   |
| C1 | CT1         | 649  | 651   |
| C2 | CT2         | 649  | 652   |
| C3 | CT3         | 649  | 653   |
| C4 | CT4         | 649  | 654   |
| C5 | CT5         | 649  | 655   |
| C6 | CT6         | 649  | 656   |
| RP | RAN Plenary | 373  | 373   |
| R1 | RAN1        | 373  | 379   |
| R2 | RAN2        | 373  | 380   |
| R3 | RAN3        | 373  | 381   |
| R4 | RAN4        | 373  | 382   |
| R5 | RAN5        | 373  | 657   |
| R6 | RAN6        | 373  | 843   |

Note: The table columns `tbid` and `SubTB` are 3GPP-internal identifiers and should be used in the implementation as primary key values in the corresponding tables.

Example 1: The meeting information for SA4 can be found at `https://www.3gpp.org/dynareport?code=Meetings-S4.htm`.
Example 2: The meeting information for CT1 can be found at `https://www.3gpp.org/dynareport?code=Meetings-C1.htm`.
Example 3: The meeting information for RAN Plenary can be found at `https://www.3gpp.org/dynareport?code=Meetings-RP.htm`.

The resulting HTML pages contain tables with all meetings for the respective working group, including meeting name, dates, location, and other metadata. This needs to be parsed and stored in the local database for querying later.

Each table row contains several meeting-specific data and URLs:

- The column "Meeting" contains an entry with the short name of the meeting, which is itself a link to the meeting details page on the 3GPP portal. The URL is always of this form: `https://portal.3gpp.org/Home.aspx#/meeting?MtgId=<meeting_id>`, whereas `meeting_id` is a unique integer identifier (uint32) for the meeting. This meeting ID can be used to query more detailed meeting information from the 3GPP portal if needed, so it must be crawled/scraped.
- The column "Files" contains an entry "Files" with a link to the TDoc FTP directory.
- If the column "Files" is empty, it means that the meeting is not yet setup and no TDocs are available for this meeting. Skip these meetings when crawling TDocs later.

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

## Project Structure

The project follows a modular architecture with clear separation of concerns:

### Source Code Organization

```
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

### Module Design Principles

1. **Submodule Re-exports**: Both `models/` and `crawlers/` use `__init__.py` to re-export all public symbols, maintaining backward compatibility
2. **Single Responsibility**: Each file focuses on one concern (e.g., `models/tdocs.py` only contains TDoc-related models)
3. **Type Safety**: All modules use comprehensive type hints with `from __future__ import annotations`
4. **Import Pattern**: Other modules import from `tdoc_crawler.models` and `tdoc_crawler.crawlers`, not from submodules directly

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

### File Size Guidelines

When splitting modules:
- Base utilities: 20-70 lines
- Model files: 80-150 lines
- Crawler files: 150-350 lines
- CLI file: 600-900 lines (acceptable due to command definitions and helper functions)
- Database file: 900-1100 lines (acceptable due to schema + queries)

## Task

### Main Functionalities

Implement a command-line interface (CLI) for querying structured 3GPP TDoc and Meeting data via a local database.

The CLI should provide these main functionalities:

- Sync Meetings:
  - Start crawling the 3GPP portal to retrieve all meeting metadata for all working groups, store the metadata in a local SQLite database (and used later to query 3GPP resources about metadata).
  - limit number of meetings to crawl via parameter `--limit-meetings <n>` (default: all meetings). Negative numbers indicate to crawl the most recent `n` meetings.
  - limit number of meetings to crawl per working group via parameter `--limit-meetings-per-wg <n>` (default: all meetings).
  - limit number of working groups to crawl via parameter `--limit-wgs <n>` (default: all working groups).
  - support for incremental updates: only crawl for new or updated meetings since the last sync.
  - Provide logging to track the crawling process, including the number of meetings retrieved and any errors encountered.
- Querying meeting metadata and displaying the results in a structured user-friendly format like e.g., JSON, YAML, or tabular format for command line output.

- Sync TDocs:
  - Start crawling the 3GPP FTP server to retrieve all links to TDocs, use the filename stem as unique identifier, which is stored in a local SQLite database (and used later to query 3GPP resources about metadata).
  - limit number of TDocs to crawl via parameter `--limit-tdocs <n>` (default: all TDocs). Negative numbers indicate to crawl the most recent `n` TDocs.
  - limit number of meetings to crawl per working group via parameter `--limit-meetings-per-wg <n>` (default: all meetings).
  - limit number of working groups to crawl via parameter `--limit-wgs <n>` (default: all working groups).
  - support for incremental updates: only crawl for new TDocs since the last sync.
  - Provide logging to track the crawling process, including the number of TDocs retrieved and any errors encountered.
- Querying TDoc metadata and displaying the results in a structured user-friendly format like e.g., JSON, YAML, or tabular format for command line output.

- Open TDoc: Download, unzip, and open a specific TDoc in the system's default application for the file type.
  - Download: Use provided cache directory to store downloaded and unzipped TDocs (default: next to database file).
  - Unzip: Unzip the downloaded TDoc file into the cache directory, at the same location as the downloaded zip file but without the `.zip` extension. Delete `.zip` file after unzipping.
  - Open: Open the unzipped TDoc file in the system's default application for the file type (e.g., PDF viewer for PDF files, text editor for TXT files, etc.). If multiple files are present in the unzipped directory, open the first file found.
- When running the CLI and/or when testing functionality, ensure that the cache path and database file specified in section "Testing" is passed as parameter `--cache-dir <path-to-cache-dir>` correctly.
- When credentials for accessing certain 3GPP resources are required.
  - By default, these are read from environment variables named `EOL_USERNAME` and `EOL_PASSWORD`.
  - Alternatively, if these environment variables are not set, check if CLI parameters `--eol-username <username>` and `--eol-password <password>` are provided.
  - If these environment variables are not set and no CLI parameters are provided, prompt the user to input their credentials interactively.

### Scraping Meeting Metadata

- Implement a command `crawl-meetings` that initiates the crawling process for meeting metadata.
- Add a short-alias command `cm` for `crawl-meetings`.
- The crawling process should:
  - Connect to the 3GPP portal, iterate over all pages of each working group (see section "Meetings").
  - Retrieve all meeting metadata (parse HTML tables per page) for all working groups.
  - Store the retrieved metadata in a local SQLite database.
  - Handle network errors and retries gracefully.
  - Log progress and any issues encountered during the crawling process.
  - Ensure that the database schema is well-defined and optimized for querying meeting metadata later.

### Crawling TDocs from Meetings

- Implement a command `crawl-tdocs` that initiates the TDoc crawling process.
- Add a short-alias command `ct` for `crawl-tdocs`.
- **Prerequisites:** The meetings database must be populated first via `crawl-meetings`. If no meetings are available, the command should display an error/warning instructing the user to run `crawl-meetings` first.
- The crawling process should:
  - Query meetings from the local database based on filters (working groups, subgroups, meeting IDs, date ranges).
  - For each meeting with a `files_url`:
    - List all files in the FTP/HTTP directory specified by `files_url`.
    - Extract candidate TDoc files (matching naming pattern, typically `.zip` extension).
    - For each candidate file, extract the TDoc ID from the filename stem.
    - Validate the TDoc by querying the 3GPP portal at `https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=<tdoc_id>`.
    - If validation succeeds, parse metadata from the portal page and store in database.
    - If validation fails, cache the negative result to avoid re-checking.
  - Handle network errors gracefully: log warnings but continue processing remaining meetings/TDocs.
  - Support parallel processing (default: 4 workers) for improved performance.
  - Support incremental mode: skip already processed meetings and TDocs unless override flag is set.
  - Support re-validation mode: re-check existing TDocs when override flag is set.
- The CLI should provide options to:
  - Filter by working group(s) via `--working-group` / `-w`
  - Filter by subgroup(s) via `--sub-group` / `-s`
  - Filter by specific meeting ID(s) via `--meeting-ids`
  - Filter by date range via `--start-date` and `--end-date`
  - Set number of parallel workers via `--workers` (default: 4)
  - Enable full re-validation via `--force-revalidate`
  - Specify cache directory and database file location
- Implement logging to track the crawling process, including:
  - Number of meetings processed
  - Number of TDocs discovered
  - Number of TDocs validated successfully
  - Number of invalid TDocs (cached)
  - Any errors encountered

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

**Portal Metadata Fields:**

When validating a TDoc via the portal page, parse the following fields:
- **Meeting** (required): The meeting identifier
- **Is revision of** (optional): Reference to previous TDoc version
- **Title** (required): Document title
- **Contact** (required): Contact person/organization
- **TDoc type** (required): Document type classification
- **For** (required): Purpose (agreement, discussion, information, etc.)
- **Agenda item** (required): Associated agenda item
- **Status** (required): Document status

All other fields are optional and may be added as needed.

### Querying TDoc Metadata

- Implement a default command that allows users to query TDoc metadata from the local SQLite database.
- If TDoc number(s) and/or its metadata are not yet present in the database, the CLI should automatically trigger the crawling process to fetch and store the required data before performing the query. See also section "Crawling 3GPP FTP Server" how to implement this.
- The CLI should provide options to specify query parameters and output format.
- The CLI should provide options to specify the cache directory and database file location.
- The CLI should allow users to filter TDocs based on various criteria (e.g., date range, document type, working group).
- The CLI should allow users to query multiple TDocs at once.
- The TDoc number(s) provided should always be treated as **case-insensitive**.
- The querying functionality should:
  - Accept various query parameters (e.g., TDoc identifier, date range, document type).
  - Retrieve relevant metadata from the SQLite database based on the provided parameters.
  - Display the results in a structured and user-friendly format (e.g., JSON, YAML, or tabular format).
  - Handle cases where no results are found gracefully.
  - Provide options for output formatting (e.g., pretty-printing JSON, selecting specific fields to display).

## CLI Commands Implementation

The CLI provides 6 commands implemented using Typer. Here are the exact signatures and key parameters:

### 1. `query-tdocs` (Default Command)

Query TDoc metadata from the database. If TDoc is not found, automatically triggers targeted fetch.

```python
@app.command()
def query(
    tdoc_ids: Annotated[list[str], typer.Argument(...)],
    working_group: Annotated[list[WorkingGroup] | None, typer.Option("--working-group", "-w")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.TABLE,
    cache_dir: Annotated[Path | None, typer.Option(...)] = None,
    db_file: Annotated[Path | None, typer.Option(...)] = None,
    eol_username: Annotated[str | None, typer.Option(...)] = None,
    eol_password: Annotated[str | None, typer.Option(...)] = None,
)
```

**Key Features**:
- Accepts multiple TDoc IDs (case-insensitive)
- Supports filtering by working group(s)
- Output formats: `table`, `json`, `yaml`, `csv`
- Auto-fetch: If TDoc not in DB, triggers targeted fetch

### 2. `crawl-tdocs`

Crawl TDocs from FTP directories based on meeting metadata.

```python
@app.command()
def crawl(
    working_group: Annotated[list[WorkingGroup] | None, typer.Option("--working-group", "-w")] = None,
    sub_group: Annotated[list[str] | None, typer.Option("--sub-group", "-s")] = None,
    meeting_ids: Annotated[list[int] | None, typer.Option("--meeting-ids")] = None,
    start_date: Annotated[str | None, typer.Option(...)] = None,
    end_date: Annotated[str | None, typer.Option(...)] = None,
    limit_meetings: Annotated[int | None, typer.Option(...)] = None,
    limit_tdocs: Annotated[int | None, typer.Option(...)] = None,
    workers: Annotated[int, typer.Option(...)] = 4,
    force_revalidate: Annotated[bool, typer.Option("--force-revalidate")] = False,
    cache_dir: Annotated[Path | None, typer.Option(...)] = None,
    db_file: Annotated[Path | None, typer.Option(...)] = None,
    eol_username: Annotated[str | None, typer.Option(...)] = None,
    eol_password: Annotated[str | None, typer.Option(...)] = None,
)
```

**Key Features**:
- Filters: working group, subgroup, meeting IDs, date range
- Limits: meetings and TDocs per crawl
- Parallel processing: `--workers` (default: 4)
- Force revalidation: Re-check existing TDocs
- Requires meetings DB to be populated first

### 3. `crawl-meetings`

Crawl meeting metadata from 3GPP portal.

```python
@app.command(name="crawl-meetings")
def crawl_meetings(
    working_group: Annotated[list[WorkingGroup] | None, typer.Option("--working-group", "-w")] = None,
    limit_meetings: Annotated[int | None, typer.Option(...)] = None,
    limit_meetings_per_wg: Annotated[int | None, typer.Option(...)] = None,
    force_update: Annotated[bool, typer.Option("--force-update")] = False,
    cache_dir: Annotated[Path | None, typer.Option(...)] = None,
    db_file: Annotated[Path | None, typer.Option(...)] = None,
    eol_username: Annotated[str | None, typer.Option(...)] = None,
    eol_password: Annotated[str | None, typer.Option(...)] = None,
)
```

**Key Features**:
- Filter by working group(s)
- Limit total meetings or per working group
- Incremental updates: Skip existing unless `--force-update`
- Prerequisite for `crawl-tdocs` command

### 4. `query-meetings`

Query meeting metadata from database.

```python
@app.command(name="query-meetings")
def query_meetings(
    working_group: Annotated[list[WorkingGroup] | None, typer.Option("--working-group", "-w")] = None,
    sub_group: Annotated[list[str] | None, typer.Option("--sub-group", "-s")] = None,
    meeting_ids: Annotated[list[int] | None, typer.Option("--meeting-ids")] = None,
    start_date: Annotated[str | None, typer.Option(...)] = None,
    end_date: Annotated[str | None, typer.Option(...)] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.TABLE,
    sort_by: Annotated[str, typer.Option(...)] = "start_date",
    sort_order: Annotated[SortOrder, typer.Option(...)] = SortOrder.DESC,
    cache_dir: Annotated[Path | None, typer.Option(...)] = None,
    db_file: Annotated[Path | None, typer.Option(...)] = None,
)
```

**Key Features**:
- Filters: working group, subgroup, meeting IDs, date range
- Sorting: By any field, ascending/descending
- Output formats: `table`, `json`, `yaml`, `csv`

### 5. `open`

Download, unzip, and open a TDoc file.

```python
@app.command()
def open_tdoc(
    tdoc_id: Annotated[str, typer.Argument(...)],
    cache_dir: Annotated[Path | None, typer.Option(...)] = None,
    db_file: Annotated[Path | None, typer.Option(...)] = None,
    eol_username: Annotated[str | None, typer.Option(...)] = None,
    eol_password: Annotated[str | None, typer.Option(...)] = None,
)
```

**Key Features**:
- Downloads TDoc from FTP if not cached
- Unzips to cache directory (deletes .zip after)
- Opens in system default application
- Case-insensitive TDoc ID

### 6. `stats`

Display database statistics.

```python
@app.command()
def stats(
    cache_dir: Annotated[Path | None, typer.Option(...)] = None,
    db_file: Annotated[Path | None, typer.Option(...)] = None,
)
```

**Key Features**:
- Shows: Total TDocs, validated TDocs, meetings, working groups
- Displays breakdown by working group
- Shows recent crawling activity

### Common Patterns

**Default Values**:

| Parameter | Default | Environment Variable |
|-----------|---------|---------------------|
| `cache_dir` | `./cache` | `TDOC_CACHE_DIR` |
| `db_file` | `{cache_dir}/tdoc_crawler.db` | `TDOC_DB_FILE` |
| `eol_username` | None | `EOL_USERNAME` |
| `eol_password` | None | `EOL_PASSWORD` |
| `output_format` | `table` | - |
| `workers` | 4 | - |

**Helper Functions**:
- `resolve_cache_dir()`: Resolves cache directory from CLI/env/default
- `resolve_db_file()`: Resolves database file path
- `get_credentials()`: Gets credentials from CLI/env/prompt

**Credential Handling**:
1. Check CLI parameters (`--eol-username`, `--eol-password`)
2. Check environment variables (`EOL_USERNAME`, `EOL_PASSWORD`)
3. Prompt user interactively if not found

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

Always normalize TDoc IDs to uppercase for case-insensitive matching:

```python
def normalize_tdoc_id(tdoc_id: str) -> str:
    """Normalize TDoc ID to uppercase for case-insensitive lookup."""
    return tdoc_id.upper().strip()
```

Usage:

```python
# In database.py
def get_tdoc(self, tdoc_id: str) -> TDocRecord | None:
    """Get TDoc by ID (case-insensitive)."""
    normalized_id = normalize_tdoc_id(tdoc_id)
    # Database uses COLLATE NOCASE for case-insensitive matching
    cursor = self.conn.execute(
        "SELECT * FROM tdocs WHERE tdoc_id = ?",
        (normalized_id,)
    )
    # ...
```

## Usage of uv and project management

- Use `uv` for creating isolated Python environments instead of `virtualenv` or `venv`. This ensures consistency across different development setups and simplifies dependency management.
- Use `uv` for managing project dependencies and ensuring reproducibility across different environments.
- Use `uv` for running Python scripts within the isolated environment to ensure that the correct dependencies are used.
- Use `uv` for packaging and distributing Python applications to ensure that all dependencies are included and the application can be easily installed in different environments.
- Use `uv` for managing project configurations and settings.
- Use `uv` for running tests to ensure that the correct dependencies and configurations are used.
- Use the `uv` build backend, never use the deprecated `setuptools`.
- Use `uv add <package>` for adding new dependencies to your project.
- Use `uv remove <package>` for removing dependencies from your project.
- Use `uv sync --all-extras -U` for a full update of all dependencies, including optional extras.
- Use `uv add <package> --dev` for adding new development dependencies to your project. Do not use `project.optional-dependencies.test` in `pyproject.toml`.
- Use `uv remove <package> --dev` for removing development dependencies from your project.
- Use `uv run <script>` for running Python scripts within the isolated environment.
- Use `uv run pytest` for running tests to ensure that the correct dependencies and configurations are used.
- Use `uv build` for packaging and distributing Python applications to ensure that all dependencies are included and the application can be easily installed in different environments.
- Use `build-backend = "uv_build"` in `[build-system]` section of `pyproject.toml`.
- Add/install packages like `pytest`, `uv_build`, etc., as development dependencies using `uv add <package> --dev`.

## Python-Specific Guidelines

- Use type hints everywhere, including for function parameters and return values. Use generics where appropriate.
- Use f-strings for formatting strings.
- Use list comprehensions and dictionary comprehensions where appropriate.
- Never use the obsolete type hint `x: Optional[SomeType] = None`! Instead, always use `x: SomeType | None = None`.
- Use `is` and `is not` for comparing to `None`, not `==` or `!=`.
- Use `enumerate()` when you need both the index and the value in a loop.
- Use `with` statements when working with files to ensure proper resource management.
- Use `pathlib` for file system paths instead of `os.path`.
- Use `logging` module for logging instead of `print()`.
- Use `typer` for command-line argument parsing, sub-commands, application configuration and in general the CLI.
- Use `rich` for rich text and beautiful formatting in the terminal.
- Use `pydantic` for data validation and settings management (see also section `Database Guidelines`).
- Use `pytest` for testing (see also next section).
- Use `ruff` for code formatting.
- Use `isort` for sorting imports.
- Use `ty` for type checking.
- Never use `virtualenv` for creating isolated Python environments - always use `uv`.
- For reading/writing data from/to CSV and Excel files, use `pandas`.
  - Use the engine from `python-calamine` for reading Excel files
  - Use the engine from `xlsxwriter` for writing Excel files.
  - For performance reasons, **never** use `openpyxl` to read or write Excel files!
- Modules (single .py files) **must always** be less than 500 lines
  - If a module exceeds this limit, consider refactoring it into a new submodule.
- Functions (declaration + implementation) **must always** be less than 100 lines
  - If a function exceeds this limit, consider refactoring it into smaller functions.
- Classes (declaration + implementation) **must always** be less than 300 lines
  - Avoid using static methods in classes - use module-level functions instead.
  - If a class has too many methods, consider splitting it into multiple smaller classes with single responsibility.
  - If a class has too many attributes, consider using composition instead of inheritance.
  - If a class has too many responsibilities, consider using the Single Responsibility Principle (SRP) to refactor it into smaller classes or using mixins.
  - If a class has too many dependencies, consider using dependency injection to reduce coupling.
  - If a class has too many methods that operate on the same data, consider using the Data Transfer Object (DTO) pattern to encapsulate the data.
  - If a class has too many methods that operate on different data, consider using the Strategy pattern to encapsulate the different behaviors.
  - If a class gets too complex and/or the interaction between other objects becomes convoluted, consider using functional programming instead of object-oriented programming style.

## Database Guidelines

### General Database Principles

- Use SQLite as the database for storing TDoc and meeting metadata.
- Design the database schema to efficiently store and query TDoc and meeting metadata.
- Use appropriate indexing to optimize query performance.
- Ensure that the database schema is well-documented and easy to understand.
- Implement database migration scripts to handle schema changes over time.
- Use `pydantic` dataclasses to define the database schema and ensure data integrity.
- Use `pydantic` models to represent database entities and ensure data integrity.

### Complete Database Schema

The database consists of five tables with proper foreign key relationships:

#### 1. Reference Tables: `working_groups` and `subworking_groups`

```sql
CREATE TABLE IF NOT EXISTS working_groups (
    tbid INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ftp_identifier TEXT NOT NULL UNIQUE,
    meetings_code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subworking_groups (
    sub_tb INTEGER PRIMARY KEY,
    tbid INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (tbid) REFERENCES working_groups(tbid)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_subworking_groups_tbid_name
    ON subworking_groups(tbid, name);
```

**Purpose**: Store the static hierarchy of 3GPP working groups and their subgroups.

**Initialization**: These tables are populated at application startup from the `WorkingGroup` enum and `SUBWORKING_GROUPS` list in `models/working_groups.py` and `models/subworking_groups.py`.

#### 2. Meetings Table: `meetings`

```sql
CREATE TABLE IF NOT EXISTS meetings (
    meeting_id INTEGER PRIMARY KEY,
    sub_tb INTEGER NOT NULL,
    meeting_name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    location TEXT,
    files_url TEXT,
    last_crawled TEXT,
    FOREIGN KEY (sub_tb) REFERENCES subworking_groups(sub_tb)
);

CREATE INDEX IF NOT EXISTS idx_meetings_sub_tb ON meetings(sub_tb);
CREATE INDEX IF NOT EXISTS idx_meetings_dates ON meetings(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_meetings_last_crawled ON meetings(last_crawled);
```

**Key Fields**:
- `meeting_id`: 3GPP's unique meeting identifier (integer)
- `sub_tb`: Foreign key to subworking_groups
- `files_url`: HTTP URL to FTP directory containing TDocs
- `last_crawled`: ISO timestamp when meeting was last processed for TDocs

#### 3. TDocs Table: `tdocs`

```sql
CREATE TABLE IF NOT EXISTS tdocs (
    tdoc_id TEXT PRIMARY KEY COLLATE NOCASE,
    meeting_id INTEGER NOT NULL,
    title TEXT,
    contact TEXT,
    tdoc_type TEXT,
    for_value TEXT,
    agenda_item TEXT,
    status TEXT,
    is_revision_of TEXT COLLATE NOCASE,
    file_url TEXT NOT NULL,
    validated BOOLEAN NOT NULL DEFAULT 0,
    last_validated TEXT,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id),
    FOREIGN KEY (is_revision_of) REFERENCES tdocs(tdoc_id)
);

CREATE INDEX IF NOT EXISTS idx_tdocs_meeting_id ON tdocs(meeting_id);
CREATE INDEX IF NOT EXISTS idx_tdocs_validated ON tdocs(validated);
CREATE INDEX IF NOT EXISTS idx_tdocs_last_validated ON tdocs(last_validated);
CREATE INDEX IF NOT EXISTS idx_tdocs_is_revision_of ON tdocs(is_revision_of);
```

**Key Fields**:
- `tdoc_id`: TDoc identifier (e.g., "R1-2301234"), case-insensitive primary key
- `validated`: Boolean flag indicating if metadata was successfully retrieved from portal
- `last_validated`: ISO timestamp of last validation attempt
- `is_revision_of`: Reference to previous TDoc version (self-referencing FK)

**Critical Design Decisions**:
- `COLLATE NOCASE` ensures case-insensitive uniqueness and lookups
- `validated=False` indicates either not yet validated OR validation failed (negative caching)
- Self-referencing foreign key for revision tracking

#### 4. Crawl Log Table: `crawl_log`

```sql
CREATE TABLE IF NOT EXISTS crawl_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    meeting_id INTEGER NOT NULL,
    tdocs_discovered INTEGER NOT NULL DEFAULT 0,
    tdocs_validated INTEGER NOT NULL DEFAULT 0,
    tdocs_failed INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id)
);

CREATE INDEX IF NOT EXISTS idx_crawl_log_meeting_id ON crawl_log(meeting_id);
CREATE INDEX IF NOT EXISTS idx_crawl_log_timestamp ON crawl_log(timestamp);
```

**Purpose**: Track crawling operations for statistics and diagnostics.

### Pydantic Models

Each table has corresponding Pydantic models:

- **Record Models** (e.g., `TDocRecord`, `MeetingRecord`): Represent database rows with all fields, used for database I/O
- **Metadata Models** (e.g., `TDocMetadata`, `MeetingMetadata`): Represent domain entities, used for API responses and business logic

**Example Pattern**:

```python
class TDocRecord(BaseModel):
    """Database row representation with all fields"""
    tdoc_id: str
    meeting_id: int
    title: str | None = None
    # ... all database columns

class TDocMetadata(BaseModel):
    """Domain entity with computed/joined fields"""
    tdoc_id: str
    meeting_name: str  # Joined from meetings table
    working_group: WorkingGroup  # Computed from sub_tb
    # ... business logic fields
```

### Database Helper Methods

The `TDocDatabase` class provides typed wrappers for all database operations:

**Key Methods**:
- `initialize_reference_tables()`: Populate working_groups and subworking_groups
- `insert_meeting()` / `get_meeting()`: Meeting CRUD operations
- `insert_tdoc()` / `get_tdoc()`: TDoc CRUD operations with case-insensitive lookup
- `mark_tdoc_validated()`: Update validation status after portal check
- `query_tdocs()`: Complex queries with filters (working group, meeting, date range)
- `get_stats()`: Aggregated statistics for CLI `stats` command

**Critical Patterns**:
- Always use parameterized queries (never string interpolation)
- Return Pydantic models, not raw tuples
- Handle case-insensitive TDoc IDs via `COLLATE NOCASE` and `.upper()` normalization

## Testing

- Use `pytest` for writing and running tests.
- After adding new or updating existing features, include pytest-based unit tests/test functions.
- Aim for high test coverage to ensure code reliability and facilitate future changes.
- Regularly run tests to catch issues early and ensure code quality.
- Refactor tests as needed to keep them maintainable and aligned with code changes.
- Use fixtures and parameterized tests to reduce code duplication and improve test coverage.
- Leverage mocking and patching to isolate tests and avoid dependencies on external systems.
- When credentials for accessing certain 3GPP resources are required during coding or testing, ...
  - Use environment variables named `EOL_USERNAME` and `EOL_PASSWORD` to provide these credentials.
  - If an `.env` file is available in the project root, load the environment variables from this file.
  - Check for a possible override via CLI parameters `--eol-username <username>` and `--eol-password <password>`.
- Any example data for tests should be included in a `tests/data` folder.
- When running tests, ensure that the cache path and database file specified in section "Testing" is used correctly.
- Use the following cache directory and database file for testing purposes:
  - Cache directory: `./tests/test-cache`
  - Database file: `./tests/test-cache/tdoc_crawler.db`

### Test Structure

The test suite is organized into several categories:

1. **Unit Tests** (`test_models.py`, `test_database.py`): Test individual functions and classes in isolation
2. **Integration Tests** (`test_crawler.py`): Test crawler logic with mocked HTTP
3. **End-to-End Tests** (`test_cli.py`): Test full CLI commands using `typer.testing.CliRunner`
4. **Feature Tests** (`test_targeted_fetch.py`): Test complex features like targeted fetch

### Standard Test Fixtures

All tests share common fixtures defined in `conftest.py`:

```python
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
            # ... other fields
        ),
        # ... more samples
    ]
```

### Mock Patterns

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

## Documentation

### Code Documentation

- Write clear and concise docstrings for all functions, classes, and modules using the Google style.
- Include type hints in docstrings for function parameters and return values.
- Use examples in docstrings to illustrate how to use functions and classes.
- Ensure that the code is well-commented to explain complex logic and decisions.

### User Documentation

#### Documentation Structure

The project maintains three levels of documentation:

1. **README.md** - Project overview, installation, basic usage
2. **docs/QUICK_REFERENCE.md** - Comprehensive command reference (MUST be kept current)
3. **docs/history/** - Chronological changelog of all significant changes

#### Critical Rules

- `docs/QUICK_REFERENCE.md` **MUST** always be up to date and reflect the current state of ALL commands
- `README.md` **MUST** contain a link to `docs/QUICK_REFERENCE.md` in a "## Quick Reference" section
- When adding or modifying commands, **BOTH** the history file **AND** `docs/QUICK_REFERENCE.md` must be updated
- History files document the change; QUICK_REFERENCE.md remains the single source of truth for command usage

#### Documentation Workflow

**When adding/modifying features:**

1. **Implement** the feature in code
2. **Create** history file documenting the change in `docs/history/YYYY-MM-DD_SUMMARY_<NN>_<topic>.md`. `<NN>` is a sequential number for multiple changes on the same day.
3. **Update** `docs/QUICK_REFERENCE.md` immediately with the new/changed command documentation
4. **Verify** `README.md` still links to `docs/QUICK_REFERENCE.md`
5. **Test** that all examples in documentation work correctly

**Example workflow for adding a new command:**

```
1. Implement: src/tdoc_crawler/cli.py - add new command
2. Test: tests/test_cli.py - add tests
3. Document in history: docs/history/2025-01-15_SUMMARY_01_NEW_VALIDATE_COMMAND.md
4. Update main reference: docs/QUICK_REFERENCE.md - add command documentation
5. Verify: README.md contains link to QUICK_REFERENCE.md
```

#### History File Naming Convention

Use this format for all history entries:

- `docs/history/YYYY-MM-DD_SUMMARY_<NN>_<topic>.md` - Summary of changes/features (NN = sequential number for multiple changes on same day)
- `docs/history/YYYY-MM-DD_REVIEW_<topic>.md` - Review/analysis of changes. Should not be committed to repository (can be deleted after review).
- `docs/history/YYYY-MM-DD_QUICK_REFERENCE_<topic>.md` - Temporary draft for QUICK_REFERENCE updates (merge into main file, should also not be committed).

**Examples:**

- `docs/history/2025-10-14_SUMMARY_01_INITIAL_IMPLEMENTATION.md`
- `docs/history/2025-10-14_REVIEW_INITIAL_IMPLEMENTATION.md`
- `docs/history/2025-10-15_SUMMARY_01_NEW_FEATURES.md` (for multiple features)
- `docs/history/2025-10-15_QUICK_REFERENCE_NEW_FEATURES.md` (draft content)

#### Cleanup

Any documentation generated during development/coding in the project root shall be cleaned up after use and integrated into the main documentation files:

- Move to `docs/history/` if it's a changelog/review
- Merge into `docs/QUICK_REFERENCE.md` if it's command documentation
- Integrate into `README.md` if it's general project information

---
#### General Documentation Guidelines

- use markdown formatting for headings, lists, code blocks, and links
- use clear and concise language
- use consistent terminology and naming conventions
- use gitmoji in `docs/QUICK_REFERENCE.md` and `README.md` for better visual identification of changes


## Reviews of AGENTS.md

After several implementation steps, the present file (`AGENTS.md`) might need an update. When explicitly asked, use/update the file  `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md` for that purpose. The review/update will be triggered with a prompt similar to this one:

```markdown
Please review the current code basis and think thorougly about possible changes/updates/modifications/refactoring/restructuring of the coding instruction file AGENTS.md, which would help coding assistants to (re-)generate the code basis as close as possible.
Document your review findings in the file `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`, including specific proposed changes with explanations. Avoid copying too many specific source code samples/examples into `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`. Do not update AGENTS.md directly, only document your review findings in the specified file.
```

The actual update of AGENTS.md will be done only after explicit user confirmation and after a prompt similar to this one:

```markdown
Based on the review findings in the file #file:REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md (`docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`), please update the coding instruction file AGENTS.md accordingly. Make sure to incorporate all relevant suggestions from the review document, ensuring that the updated AGENTS.md reflects the best practices and guidelines for coding assistants to (re-)generate the code basis as close as possible. Avoid copying too many specific source code samples/examples into `AGENTS.MD`. You might move the current section regarding "Reviews of AGENTS.md" to a different place, but keep it unchanged.
```
