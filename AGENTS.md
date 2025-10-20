# Assistant Rules for TDoc-Crawler - Command line tool for querying structured 3GPP TDoc data

---
description: General Guidelines
alwaysApply: true
---

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

TDocs are stored on the 3GPP FTP server and are publicly accessible to everyone. They are available at the following base URL: `https://www.3gpp.org/ftp/tsg_<working_group_identifier>/<sub-working_group_identifier>/<meeting_identifier>/Docs/<tdoc_nbr>.zip`.

Note that ...
- `<tdoc_nbr>` is the filename stem of the TDoc file, e.g., `R1-2301234`.
- the first letter of the TDoc number indicates the working group, e.g., `R` for RAN, `S` for SA, and `T` for CT.
- Any other files on the FTP server that do not follow this naming convention are not TDocs and should be ignored.
- `<sub-working_group_identifier>` and `<meeting_identifier>` are just path names and do not have a fixed format or naming convention, they also do not correspond to the official SWG and meeting identifiers (i.e., they are arbitrary path names on the FTP server and thus do not need to be stored in the database).
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

Note: The table columns `tbid` and `SubTB` are only for reference and do not need to be used in the implementation.

Example 1: The meeting information for SA4 can be found at `https://www.3gpp.org/dynareport?code=Meetings-S4.htm`.
Example 2: The meeting information for CT1 can be found at `https://www.3gpp.org/dynareport?code=Meetings-C1.htm`.
Example 3: The meeting information for RAN Plenary can be found at `https://www.3gpp.org/dynareport?code=Meetings-RP.htm`.

The resulting HTML pages contain tables with all meetings for the respective working group, including meeting name, dates, location, and other metadata. This needs to be parsed and stored in the local database for querying later.

Each table row contains several meeting-specific data and URLs:

- The column "Meeting" contains an entry with the short name of the meeting, which is itself a link to the meeting details page on the 3GPP portal. The URL is always of this form: `https://portal.3gpp.org/Home.aspx#/meeting?MtgId=<meeting_id>`, whereas `meeting_id` is a unique integer identifier (uint32) for the meeting. This meeting ID can be used to query more detailed meeting information from the 3GPP portal if needed, so it must be crawled/scraped.
- The column "Files" contains an entry "Files" with a link to the TDoc FTP directory.
- If the column "Files" is empty, it means that the meeting is not yet setup and no TDocs are available for this meeting. Skip these meetings when crawling TDocs later.

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
- The crawling process should:
  - Connect to the 3GPP portal, iterate over all pages of each working group (see section "Meetings").
  - Retrieve all meeting metadata (parse HTML tables per page) for all working groups.
  - Store the retrieved metadata in a local SQLite database.
  - Handle network errors and retries gracefully.
  - Log progress and any issues encountered during the crawling process.
  - Ensure that the database schema is well-defined and optimized for querying meeting metadata later.

### Crawling 3GPP FTP Server

- Implement a command `crawl` that initiates the crawling process.
- The crawling process should:
  - Connect to the 3GPP FTP server.
  - Retrieve all links to TDocs recursively starting from the root directory.
  - Use the filename stem as a unique identifier for each TDoc, which must follow the naming convention specified in the previous section ("Background on 3GPP TDocs").
  - Store the retrieved links and their identifiers in a local SQLite database.
  - Handle network errors and retries gracefully.
  - Log progress and any issues encountered during the crawling process.
  - Ensure that the database schema is well-defined and optimized for querying TDoc metadata later.
- The CLI should provide options to specify the cache directory and database file location.
- Ensure that the crawling process can be run periodically to update the database with new TDocs.
- Ensure that the crawling process can be run incrementally, i.e., it should not re-fetch TDocs that are already present in the database and/or only fetch new TDocs (given a specific time range or other criteria).
- Implement logging to track the crawling process, including the number of TDocs retrieved and any errors encountered.
- Ignore any files that might follow the TDoc naming convention, but are located outside the official TDoc directories on the FTP server (e.g., files in a `Docs` directory that is not part of a meeting directory), in particular:
  - `.../Inbox/...`
  - `.../Draft/...`
  - `.../Drafts/...`
  - `.../Agenda/...`
  - `.../Invitation/...`
  - `.../Report/...`

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

## Database Guidelines

- Use SQLite as the database for storing TDoc and meeting metadata.
- Design the database schema to efficiently store and query TDoc and meeting metadata.
- Use appropriate indexing to optimize query performance.
- Ensure that the database schema is well-documented and easy to understand.
- Implement database migration scripts to handle schema changes over time.
- Use `pydantic` dataclasses to define the database schema and ensure data integrity.
- Use `pydantic` models to represent database entities and ensure data integrity.

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
2. **Create** history file documenting the change in `docs/history/YYYY-MM-DD_SUMMARY_<topic>.md`
3. **Update** `docs/QUICK_REFERENCE.md` immediately with the new/changed command documentation
4. **Verify** README.md still links to QUICK_REFERENCE.md
5. **Test** that all examples in documentation work correctly

**Example workflow for adding a new command:**

```
1. Implement: tracktor_tools/cli.py - add new command
2. Test: tests/test_activities.py - add tests
3. Document in history: docs/history/2025-01-15_SUMMARY_NEW_VALIDATE_COMMAND.md
4. Update main reference: docs/QUICK_REFERENCE.md - add validate command section
5. Verify: README.md contains link to QUICK_REFERENCE.md
```

#### History File Naming Convention

Use this format for all history entries:

- `docs/history/YYYY-MM-DD_SUMMARY_<topic>.md` - Summary of changes/features
- `docs/history/YYYY-MM-DD_REVIEW_<topic>.md` - Review/analysis of changes
- `docs/history/YYYY-MM-DD_QUICK_REFERENCE_<topic>.md` - Temporary draft for QUICK_REFERENCE updates (merge into main file, then can be kept as reference)

**Examples:**

- `docs/history/2025-10-14_SUMMARY_INITIAL_IMPLEMENTATION.md`
- `docs/history/2025-10-14_REVIEW_INITIAL_IMPLEMENTATION.md`
- `docs/history/2025-10-15_SUMMARY_NEW_FEATURES.md` (for multiple features)
- `docs/history/2025-10-15_QUICK_REFERENCE_NEW_FEATURES.md` (draft content)

#### Cleanup

Any documentation generated during development/coding in the project root shall be cleaned up after use and integrated into the main documentation files:

- Move to `docs/history/` if it's a changelog/review
- Merge into `docs/QUICK_REFERENCE.md` if it's command documentation
- Integrate into `README.md` if it's general project information
