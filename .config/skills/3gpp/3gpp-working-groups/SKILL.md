---
name: 3gpp-working-groups
description: Working group nomenclature, tbid/SubTB identifiers, subgroup hierarchy, and TSG structure. Use when working with 3GPP working groups, parsing meeting codes, or understanding TBID mappings.
metadata:
  related: [3gpp-basics, 3gpp-meetings, 3gpp-tdocs]
---

# 3GPP Working Groups

## Overview

3GPP has three main Technical Specification Groups (TSGs), each with multiple Working Groups (WGs) and Sub-Working Groups (SWGs):

### TSG Structure

- **TSG RAN** (Radio Access Network)
- **TSG SA** (Service and System Aspects)
- **TSG CT** (Core Network and Terminals)

Each TSG is responsible for:

- Preparation of detailed time frame and management of each Release
- Proposal and approval of work items
- Technical coordination
- Maintenance of TSG voting list

## Working Group Identifiers

### TBID (Technical Body ID)

Each TSG has a unique `tbid` identifier used in 3GPP systems:

| TSG | tbid | FTP Root URL |
|------|------|--------------|
| RAN | 373 | <https://www.3gpp.org/ftp/tsg_ran/> |
| SA | 375 | <https://www.3gpp.org/ftp/tsg_sa/> |
| CT | 649 | <https://www.3gpp.org/ftp/tsg_ct/> |

### SubTB (Sub-Technical Body ID)

Each Working Group within a TSG has a unique `SubTB` identifier:

| TSG | WG | SubTB | Focus Area |
|------|-----|-------|-----------|
| RAN | RAN Plenary | 373 | TSG RAN overview |
| RAN | RAN1 | 379 | Radio Layer 1 (Physical layer) |
| RAN | RAN2 | 380 | Radio Layer 2/3 (Radio Resource Control) |
| RAN | RAN3 | 381 | UTRAN/E-UTRAN/NG-RAN architecture |
| RAN | RAN4 | 382 | Radio Performance and Protocol Aspects |
| RAN | RAN5 | 657 | Mobile terminal conformance testing |
| RAN | RAN6 | 843 | Radio Access Network (Legacy/Closed) |
| SA | SA Plenary | 375 | TSG SA overview |
| SA | SA1 | 384 | Services |
| SA | SA2 | 385 | System Architecture and Services |
| SA | SA3 | 386 | Security and Privacy |
| SA | SA4 | 387 | Multimedia Codecs, Systems and Services |
| SA | SA5 | 388 | Management, Orchestration and Charging |
| SA | SA6 | 825 | Application Enablement and Critical Communication Applications |
| CT | CT Plenary | 649 | TSG CT overview |
| CT | CT1 | 651 | User Equipment to Core Network protocols |
| CT | CT2 | 652 | Interworking with External Networks & Policy and Charging Control |
| CT | CT3 | 653 | Closed Group (was GERAN coordination) |
| CT | CT4 | 654 | Core Network Protocols |
| CT | CT5 | 655 | Core Network and Terminals (Architecture) |
| CT | CT6 | 656 | Smart Card Application Aspects |

## Meeting Code Convention

### Meeting URL Pattern

3GPP meeting lists use dynamic pages at:

```
https://www.3gpp.org/dynareport?code=Meetings-<ID>.htm
```

Where `<ID>` is a two-digit code:

- `RP` for RAN Plenary
- `SP` for SA Plenary
- `CP` for CT Plenary
- `R1-R6` for RAN1-RAN6 (e.g., R1, R2, etc.)
- `S1-S6` for SA1-SA6 (e.g., S1, S2, etc.)
- `C1-C6` for CT1-CT6 (e.g., C1, C2, etc.)

**Example URLs:**

- RAN meetings: `https://www.3gpp.org/dynareport?code=Meetings-RP.htm`
- SA4 meetings: `https://www.3gpp.org/dynareport?code=Meetings-S4.htm`
- CT3 meetings: `https://www.3gpp.org/dynareport?code=Meetings-C3.htm`

### Meeting Name Formats

Meeting names are **inconsistent** across years and groups:

- `SA4#134` - Standard SA4 format
- `SA4-e (AH) Audio SWG post 130` - Ad-hoc meeting
- `3GPPSA4-e (AH) Audio SWG post 130` - With 3GPP prefix
- `RAN1#98` - Standard RAN1 format
- `S4-133-e` - Alternative SA4 format

**Important**: Do NOT parse information from meeting names directly. Use database with proper `meeting_id` integer identifiers.

## TSG Working Groups Details

### RAN (Radio Access Network) - tbid 373

**Responsibilities**: Radio access technologies like LTE and 5G NR

**Working Groups:**

- **RAN Plenary** (SubTB: 373): Overall TSG RAN coordination
- **RAN1** (SubTB: 379): Radio Layer 1 (Physical layer)
- **RAN2** (SubTB: 380): Radio Layer 2/3 (Radio Resource Control)
- **RAN3** (SubTB: 381): UTRAN/E-UTRAN/NG-RAN architecture
- **RAN4** (SubTB: 382): Radio Performance and Protocol Aspects
- **RAN5** (SubTB: 657): Mobile terminal conformance testing
- **RAN6** (SubTB: 843): Radio Access Network (Legacy, closed group)

**FTP Structure:**

```
tsg_ran/
├── WG1_RL1/
├── WG2_RL2/
├── WG3_RL3/
├── WG4_RL4/
├── WG5_RL5/
└── TSG_RAN/
```

### SA (Service and System Aspects) - tbid 375

**Responsibilities**: Overall architecture, service requirements, system capabilities

**Working Groups:**

- **SA Plenary** (SubTB: 375): TSG SA coordination and overall technical work
- **SA1** (SubTB: 384): Services
- **SA2** (SubTB: 385): System Architecture and Services
- **SA3** (SubTB: 386): Security and Privacy
- **SA4** (SubTB: 387): Multimedia Codecs, Systems and Services
- **SA5** (SubTB: 388): Management, Orchestration and Charging
- **SA6** (SubTB: 825): Application Enablement and Critical Communication Applications

**FTP Structure:**

```
tsg_sa/
├── WG1_S1/
├── WG2_S2/
├── WG3_S3/
├── WG4_S4/
├── WG5_S5/
├── WG6_S6/
└── TSG_SA/
```

### CT (Core Network and Terminals) - tbid 649

**Responsibilities**: Core network protocols, interfaces, and user equipment

**Working Groups:**

- **CT Plenary** (SubTB: 649): TSG CT coordination
- **CT1** (SubTB: 651): User Equipment to Core Network protocols
- **CT2** (SubTB: 652): Interworking with External Networks & Policy and Charging Control
- **CT3** (SubTB: 653): Closed Group (was GERAN coordination)
- **CT4** (SubTB: 654): Core Network Protocols
- **CT5** (SubTB: 655): Core Network and Terminals (Architecture)
- **CT6** (SubTB: 656): Smart Card Application Aspects

**FTP Structure:**

```
tsg_ct/
├── WG1_C1/
├── WG2_C2/
├── WG3_C3/
├── WG4_C4/
├── WG5_C5/
├── WG6_C6/
└── TSG_CT/
```

## Meeting Table Structure

Each TSG meeting list page contains tables with:

- **Meeting column**: Short name (links to meeting details)
- **Files column**: Link to TDoc FTP directory (empty if not yet setup)
- **Dates column**: Start and end dates
- **Location column**: Physical location

**Critical**: If "Files" column is empty, skip that meeting for TDoc crawling.

## Usage in Code

### Normalizing Working Groups

When parsing CLI arguments or user input:

1. **Plenary Aliases** (short codes):

   - `RP` → `RAN` Plenary
   - `SP` → `SA` Plenary
   - `CP` → `CT` Plenary

1. **Subgroup Codes**:

   - Use canonical codes: `R1`, `S4`, `C1`, etc. (not `RAN1`, `SA4`, `C1`)
   - For CLI parameters, normalize `SA4` → `S4`, `RAN1` → `R1`, `CT1` → `C1`

1. **TBID Mappings** (used in database):

   - RAN groups: tbid=373, SubTB: 373-389
   - SA groups: tbid=375, SubTB: 375-388
   - CT groups: tbid=649, SubTB: 649-656

### Code Example

```python
from tdoc_crawler.models import WorkingGroup

def normalize_meeting_code(code: str) -> str:
    """Normalize meeting codes to canonical format."""
    plenary_aliases = {"RP": "RAN", "SP": "SA", "CP": "CT"}
    upper = code.upper().strip()
    
    if upper in plenary_aliases:
        return plenary_aliases[upper]
    
    # Extract prefix for subgroups (R1, S4, C1, etc.)
    # Code example: "R1" → RAN group, subgroup RAN1
    return upper[0] if len(upper) > 1 else upper

def get_tbid_from_wg(wg: WorkingGroup) -> int:
    """Get TBID from WorkingGroup enum."""
    return wg.tbid
```

## Common Patterns

### Meeting ID Resolution

When resolving portal meeting names to database meeting IDs:

1. Try exact match (case-insensitive)
1. Try normalized name match
1. Try prefix/suffix matching (handle "3GPPSA4" vs "SA4")
1. Use Levenshtein distance for minor typos

**Avoid**: Substring matching (`%SA4%`) which matches fragments

### FTP Directory Names

FTP directory names on server do NOT match official WG names:

- `WG1_RL1` vs official "RAN1"
- `WG2_RL2` vs official "RAN2"
- `TSG_RAN` vs official "RAN Plenary"

**Use official codes** (tbid/SubTB) for database lookups.

## Cross-References

- **@3gpp-basics** - For 3GPP organization and structure
- **@3gpp-meetings** - For meeting pages and naming conventions
- **@3gpp-tdocs** - For TDoc handling and FTP structure
- **@3gpp-portal-authentication** - For portal access when authentication required

## Resources

- 3GPP Groups: <https://www.3gpp.org/3gpp-groups/>
- 3GPP Portal: <https://portal.3gpp.org/>
- 3GPP Work Plan: <https://www.3gpp.org/specifications-technologies/3gpp-work-plan/>
