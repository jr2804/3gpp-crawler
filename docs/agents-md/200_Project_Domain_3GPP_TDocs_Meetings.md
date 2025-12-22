# Project Domain: 3GPP, Meetings, and TDocs (Agent Notes)

This document provides the minimum domain context required to safely modify crawling, parsing, and storage logic.

## High-level concepts

- **3GPP** produces standards via technical groups. Technical administration and infrastructure is provided by **ETSI**.
- **Meetings** are the unit that groups documents. A meeting has a 3GPP portal meeting ID (integer) and often a “Files” directory URL.
- **TDocs** (Temporary Documents) are meeting contributions that live in a directory tree on the 3GPP web server.

## Where TDocs live (HTTP “FTP” tree)

TDocs are stored on the 3GPP web server under a directory structure like:

- `https://www.3gpp.org/ftp/tsg_<working_group_identifier>/<sub-working_group_identifier>/<meeting_identifier>/Docs/<tdoc_id>.zip`

Notes:

- The server is HTTP(S) accessible; “FTP server” is historical terminology.
- The `<sub-working_group_identifier>` and `<meeting_identifier>` parts are directory names with no stable semantics; do not parse meaning from them.

## TDoc identifiers

A TDoc identifier (the filename stem) is the database primary identifier.

### Filename pattern

The crawler uses this simplified regex:

```python
TDOC_PATTERN = re.compile(r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)", re.IGNORECASE)
```

Implications:

- First character: `R` (RAN), `S` (SA), `C` (CT)
- Second character: subgroup `1`–`6` or plenary `P`
- Most TDocs are `.zip`; `.txt` and `.pdf` are rare but supported
- Treat IDs as case-insensitive in the CLI and database (normalize to uppercase when creating IDs)

### Examples

- Matches: `R1-2301234.zip`, `S4aA220001.zip`, `CP-123456.zip`
- Does not match: `R7-123456.zip` (invalid subgroup), `R1-12.zip` (too short), `README.txt` (not a TDoc)

## Working groups and meeting code pages

Meeting lists come from the “dynareport” pages:

- `https://www.3gpp.org/dynareport?code=Meetings-<ID>.htm`

Where `<ID>` is one of the codes below:

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

Operational notes:

- The `tbid`/`SubTB` values are used as primary keys for reference tables.
- A meeting row may have an empty “Files” link; those meetings should be skipped by TDoc crawling.

## Portal metadata lookup (authenticated)

When a TDoc ID is known, the portal page can be queried for metadata:

- `https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=<tdoc_id>`

Some metadata requires an ETSI Online Account (EOL). The crawler should treat authentication failures as non-fatal for discovery (log and continue).

## Links

- Human-facing CLI behavior: [docs/QUICK_REFERENCE.md](../QUICK_REFERENCE.md)
- Agent implementation patterns: [docs/agents-md/400_Crawling_and_Portal_Patterns.md](400_Crawling_and_Portal_Patterns.md)
