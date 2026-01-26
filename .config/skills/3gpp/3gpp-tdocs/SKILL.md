---
name: 3gpp-tdocs
description: TDoc patterns, filename conventions, metadata structure, HTTP/FTP server access, and TDoc identification. Use when crawling TDocs from FTP directories, parsing TDoc metadata from portal, or validating TDoc numbers.
metadata:
  related: [3gpp-working-groups, 3gpp-meetings, 3gpp-portal-authentication]
---

# TDocs (Temporary Documents)

## Quick Reference

| Pattern | Example | WG | Subgroup |
|---------|---------|----|----------|
| R1-xxxx | R1-2301234 | RAN | 1 |
| RP-xxxx | RP-230045 | RAN | Plenary |
| S4-xxxx | S4-251209 | SA | 4 |
| SP-xxxx | SP-240001 | SA | Plenary |
| C1-xxxx | C1-2345678 | CT | 1 |
| CP-xxxx | CP-123456 | CT | Plenary |

**Regex:** `[RSC][1-6P].{4,10}\.(zip|txt|pdf)`

## Overview

TDocs are meeting documents produced by members participating in 3GPP Working Groups and Sub-Working Groups. They include proposals, reports, and other documents related to the development of 3GPP standards.

## TDoc Allocation

Every TDoc is always allocated to a specific 3GPP meeting.

## TDoc Number Format

### Pattern

**Regex Pattern:**

```python
TDOC_PATTERN = re.compile(r"([RSC][1-6P].{4,10})\.(zip|txt|pdf)", re.IGNORECASE)
```

### Breakdown

| Part | Pattern | Description |
|-------|---------|-------------|
| **1st char** | `[RSC]` | Working group: R (RAN), S (SA), C (CT) |
| **2nd char** | `[1-6P]` | Subgroup: 1-6 for WGs, or P for Plenary |
| **3rd part** | `.{4,10}` | 4-10 identifier characters |
| **Extension** | `\.(zip|txt|pdf)` | Required file extension |

### Examples that Match

**Standard format:**

- `R1-2301234.zip` - RAN1 TDoc
- `S4-251209.txt` - SA4 TDoc
- `C1-2345678.pdf` - CT1 TDoc

**Plenary format:**

- `RP-230045.txt` - RAN Plenary TDoc
- `SP-240001.zip` - SA Plenary TDoc
- `CP-123456.zip` - CT Plenary TDoc

**Ad-hoc format:**

- `S4aA220001.zip` - SA4 ad-hoc meeting
- `R1eE230045.txt` - RAN1 ad-hoc meeting

**Case variations:**

- `r1-2301234.ZIP` - Case-insensitive matching
- `S4-251209.TXT` - Case-insensitive matching

### Examples that Don't Match

**Wrong working group:**

- `T1-2300456.zip` - T is invalid (use C for CT)
- `X1-2300456.zip` - X is invalid (use R, S, or C)

**Wrong subgroup:**

- `R7-2300456.zip` - Subgroup 7 doesn't exist (1-6 only)
- `R1-12.zip` - Only 2 characters after R1 (need 4-10)
- `R1-12345678901.zip` - 11 characters, exceeds maximum of 10

**Wrong extension:**

- `R1-2301234.doc` - Invalid extension (must be .zip, .txt, or .pdf)
- `R1-2301234` - Missing extension

**Not a TDoc:**

- `README.txt` - Not a TDoc
- `data.csv` - Not a TDoc
- `agenda.zip` - Administrative file, not a TDoc

## TDoc FTP/HTTP Server Access

### Server Structure

3GPP maintains a file server at FTP-like HTTP URLs:

```
https://www.3gpp.org/ftp/tsg_<working_group_identifier>/
```

### FTP Root URLs by Working Group

| Working Group | Identifier | FTP Root URL |
|--------------|-------------|------------|
| RAN | `ran` | `https://www.3gpp.org/ftp/tsg_ran/` |
| SA | `sa` | `https://www.3gpp.org/ftp/tsg_sa/` |
| CT | `ct` | `https://www.3gpp.org/ftp/tsg_ct/` |

### TDoc URL Pattern

TDocs are available at:

```
https://www.3gpp.org/ftp/tsg_<wg>/<sub-working_group_identifier>/<meeting_identifier>/Docs/<tdoc_nbr>.zip
```

**URL Components:**

- `tsg_<wg>` - Working group root (e.g., `tsg_ran`, `tsg_sa`)
- `<sub-working_group_identifier>` - Arbitrary path name (NOT official subgroup ID)
- `<meeting_identifier>` - Arbitrary path name (NOT official meeting ID)
- `Docs/` - Typical subdirectory containing TDocs (case-insensitive)
- `<tdoc_nbr>` - TDoc filename stem
- `.zip` - File extension (99%+ of TDocs)

### Example URLs

```
RAN WG1 TDoc R1-2301234:
https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/R1-2301234.zip

SA4 TDoc S4-251209:
https://www.3gpp.org/ftp/tsg_sa/WG4_S4/SA4_134/Docs/S4-251209.zip
```

**Important Notes:**

- Server uses HTTP protocol, not FTP (accessible via standard HTTP requests)
- `<sub-working_group_identifier>` and `<meeting_identifier>` are arbitrary path names, do NOT correspond to official IDs
- More than 99% of TDocs are `.zip` format
- Rare cases use `.pdf` or `.txt` extension

## TDoc Subdirectory Detection

### Problem

TDocs are typically stored in subdirectories like "Docs/" rather than directly in the base meeting directory.

### Detection Process

1. **Fetch base meeting directory** from `files_url`
1. **Parse HTML** to extract directory links
1. **Check for TDoc subdirectories** (case-insensitive matching)
1. **If subdirectories found**: Crawl each subdirectory
1. **If no subdirectories**: Crawl base directory directly

### TDoc Subdirectories

**Common subdirectory names** (case-insensitive matching):

- `Docs/`
- `Documents/`
- `Tdocs/`
- `TDocs/`
- `DOCS/`

### Excluded Directories

Non-TDoc directories to skip during crawling:

```
EXCLUDED_DIRS = {"Inbox", "Draft", "Drafts", "Agenda", "Invitation", "Report"}
```

## TDoc Direct Links

### Portal TDoc View URL

When TDoc number is known, use 3GPP portal to query metadata:

```
https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=<tdoc_nbr>
```

**Example:**

```
https://portal.3gpp.org/ngppapp/CreateTdoc.Aspx?mode=view&contributionUid=R1-2301234
```

## TDoc Metadata Fields

When validating TDocs via portal page, parse these fields:

### Required Fields

- **title**: Document title
- **meeting**: The meeting identifier (e.g., "SA4#133")
- **contact**: Contact person
- **source**: Responsible organization
- **tdoc_type**: Document type classification
- **for**: Purpose (agreement, discussion, information, etc.)
- **agenda_item**: Associated agenda item (split into `agenda_item_nbr` and `agenda_item_title`)
- **status**: Document status

### Optional Fields

- **is_revision_of**: Reference to previous TDoc version (self-referencing FK)

### Metadata Parsing

1. **Ensure authenticated** with 3GPP portal before fetching
1. **Fetch portal page** with mode=view parameter
1. **Parse HTML** using BeautifulSoup
1. **Extract form fields** (labels and values)
1. **Handle agenda_item split**: Separate number and title
1. **Return dictionary** of key-value pairs

### Code Pattern

```python
from bs4 import BeautifulSoup

def parse_tdoc_metadata(html_content: str, tdoc_id: str) -> dict[str, str]:
    """Parse TDoc metadata from portal HTML page."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    metadata = {}
    
    # Parse form fields (simplified example)
    for label in soup.find_all("label"):
        value_element = label.find_next_sibling("input")
        if value_element and value_element.get("value"):
            field_name = label.get_text().strip(": ").lower()
            metadata[field_name] = value_element.get("value")
    
    return metadata
```

## TDoc ID Normalization

Always normalize TDoc IDs to uppercase for case-insensitive matching and database lookups:

```python
def normalize_tdoc_id(tdoc_id: str) -> str:
    """Normalize TDoc ID to uppercase for case-insensitive lookup."""
    return tdoc_id.upper().strip()
```

### Example

```python
# User input (any case)
tdoc_id = "r1-2301234"

# Normalized for database/storage
normalized_id = normalize_tdoc_id("r1-2301234")  # Returns "R1-2301234"
```

## Usage in Code

### When Crawling TDocs

1. **Use TDOC_PATTERN** to match files in HTTP directory listings
1. **Extract TDoc ID** from filename stem using `group(1)` of regex match
1. **Store normalized ID** (uppercase) in database
1. **Build full HTTP URL** to TDoc file
1. **Validate via portal** if needed (uses `3gpp-portal-authentication` skill)

### Example Implementation

```python
import re
from bs4 import BeautifulSoup
import requests

# Match TDoc file
match = TDOC_PATTERN.search(href)
if match:
    tdoc_id = match.group(1).upper()
    full_url = base_url + match.group(0)
    
    # Later validate via portal
    metadata = fetch_tdoc_metadata(tdoc_id, credentials)
```

## Working Group Inference

Infer working group from TDoc ID first character:

| First Char | Working Group |
|-----------|---------------|
| R | RAN |
| S | SA |
| C | CT |

```python
def infer_working_group_from_tdoc(tdoc_id: str) -> str | None:
    """Infer working group from TDoc ID."""
    mapping = {"R": "RAN", "S": "SA", "C": "CT"}
    return mapping.get(tdoc_id[0].upper(), None)
```

## Cross-References

- **@3gpp-working-groups** - For understanding working group and subgroup structure
- **@3gpp-meetings** - For understanding how TDocs are associated with meetings
- **@3gpp-portal-authentication** - For accessing TDoc metadata from portal

## Key Points

- **Case-insensitive**: TDoc IDs should be normalized to uppercase for database operations
- **99%+ .zip files**: Most TDocs use `.zip` format
- **Public FTP access**: Files are publicly accessible without authentication
- **Portal metadata**: Requires EOL account for detailed metadata
- **Subdirectory handling**: Always check for Docs/, Documents/, etc. before crawling base directory
- **Excluded directories**: Skip Inbox/, Draft/, Agenda/, Invitation/, Report/ as they are not TDocs

## Resources

- **3GPP Official:** <https://www.3gpp.org/>
- **3GPP Portal:** <https://portal.3gpp.org/>
- **3GPP FTP:** <https://www.3gpp.org/ftp/>
