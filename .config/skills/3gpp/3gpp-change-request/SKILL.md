______________________________________________________________________

## name: 3gpp-change-request description: Change Request procedure, workflow, status tracking, CR database, and step-by-step instructions. Use when working with 3GPP Change Requests to modify specifications, understanding CR lifecycle, or querying CR status. metadata: related: [3gpp-specifications, 3gpp-basics, 3gpp-working-groups, 3gpp-tdocs, 3gpp-portal-authentication, 3gpp-releases]

# 3GPP Change Requests - Reference

> **Quick Start**: For workflow overview and submission checklist, see [workflow.md](workflow.md).

## Overview

Change Requests (CRs) are documents submitted to 3GPP Working Groups to create revised versions of specifications. They represent the formal mechanism for modifying 3GPP specs after initial approval.

## What is a CR?

A CR is a **temporary document** (tdoc) to a meeting which specifies in precise detail changes to be made to a specification. It consists of:

- **CR Cover Sheet**: Describes why a change is needed and summarizes how the change is made
- **Attached Parts of Spec**: Word™ "Track Changes" (revision marks) identifying affected sections
- **Summary of Changes**: Brief explanation of the proposed modification

## Why Changes Are Needed

Three main reasons for creating a CR:

1. **Add a new feature** to a Release still under development
1. **Correct / clarify / enhance** an existing feature in a Release still under development
1. **Correct an error** in a spec which is functionally frozen

## CR Development and Approval

### Submission Process

1. **WG Level**: Any 3GPP member organization can propose a CR to the Working Group responsible for the spec
1. **WG Agreement**: WG discusses and agrees CR is valid and required
1. **TSG Approval**: WG presents CR to parent TSG plenary for final approval
1. **MCC Incorporation**: After TSG approval, 3GPP Support Team (MCC) incorporates CR into new spec version

### CR Status Meanings

| Status | TSG | WG | Meaning |
|---------|-----|----|--------|
| use | YES | YES | Valid for use |
| agreed | - | YES | WG agreed, forward to TSG |
| approved | YES | NO | Final decision (implemented) |
| rejected | YES | YES | Sustained objection |
| revised | YES | YES | Modified to new revision |
| merged | YES | YES | Combined with other CRs |
| postponed | YES | YES | Deferred to later date |
| endorsed | NO | YES | WG consensus, technically correct |
| withdrawn | YES | YES | Retracted before discussion |
| reissued | NO | NO | Recast unchanged in another TSG |
| noted | NO | NO | Deprecated (ambiguous term) |

## CR Number Format

```
<specnumber_no_dot>*_CR*<4-character_CR_number>*[r*<revision_number>*]
```

**Components:**

- `<specnumber_no_dot>`: Spec number without dot (e.g., `21.456` for TS 21.456)
- `*`: Literal asterisk
- `<4-character_CR_number>`: 4-digit CR number padded with leading zeros (e.g., `0095`)
- `[r*<revision_number>*]`: Lowercase 'r' + revision number (only for revised CRs)
- `<release>`: Release identifier (Rel-4, Rel-5, etc.)

**Examples:**

- Initial: `31.102_0095` - CR 0095 to spec 31.102
- First revision: `31.102_0095_r1` - Revision 1 of spec 31.102
- Mirror CR: `31.103_0095` - Mirrored CR to spec 31.103

## CR Database

### Netovate Search Tool

3GPP has an agreement with Netovate to provide a free CR database search:

- **URL**: <http://netovate.com/cr-search/>
- **Access**: Free web-based search tool
- **Features**: Search by spec number, CR number, or status

### 3GPP CR Database

Available on 3GPP FTP:

- **Directory**: `/ftp/Information/Databases/Change_Request/`
- **Format**: MS Access™ (.mdb) database
- **Access**: Direct download or via portal

### CR Status Tracking

Each spec maintains a history box listing all CRs that have been approved for that specification.

## Step-by-Step Instructions

3GPP provides detailed step-by-step instructions for writing CRs:

- **URL**: <https://www.3gpp.org/specifications-technologies/specifications-by-series/change-requests-step-by-step>

**Key Sections:**

1. Header (meeting details, WG document number)
1. Spec number, CR number
1. CR revision number (for revised CRs only)
1. Current version
1. Title
1. Source to WG
1. Source to TSG
1. Work item code
1. Date
1. Category
1. Release
1. Consequences if not approved
1. Clauses affected
1. Other specs affected
1. Other comments
1. CR revision history
1. Filename convention
1. Body of CR
1. Other considerations

## CR Categories

CRs are classified by category to indicate their nature:

- **Category F (Corrective)**: Corrective CRs, typically to earliest Release version
- **Category A (Mirror)**: Mirrors of CRs to previous Release versions
- **Mirror CRs require**: Same WI code per Release
- **Mirror CRs are marked**: Category A in spec history

### Category Definitions

| Category | Description |
|-----------|-------------|
| F | Corrective CRs applied to earliest Release version |
| A | Mirror CRs of same spec to different Release version |
| TEI | Technical Enhancement or Improvement |

## Important CR Concepts

### Mirror CRs

For specs maintained in multiple parallel Releases:

- Each Release needs its own mirror CR
- Use same WI code (Work Item code) for all mirror CRs
- Example: Spec 21.456 has mirror CRs in Release 4, Release 5, etc.

### Corrective Release 7 CRs

Special category for early LTE (Release 7) features that need to work on both Release 4 and Release 5 specs.

### Editorial Updates

CRs for pure editorial changes (no technical content) are typically implemented by MCC as "dot-one" versions (e.g., 21.456.1) rather than full CRs.

## Work Items

Each CR must be associated with a **Work Item (WI) code**:

- Obtained from official WI list: <https://www.3gpp.org/ftp/Specs/html-info/WI-List.htm>
- **Format**: 6-digit numeric code (e.g., `123456`)
- **Purpose**: Justifies the new feature or modification

## CR Submission Checklist

1. [ ] Unique_ID value from Work Item
1. [ ] TDoc number of Work Item Description (WID) document
1. [ ] Name of rapporteur for TS/TR (or contact coords for TR)
1. [ ] Target date from WID (approval date)
1. [ ] Source to WG (responsible 3GPP member)
1. [ ] Source to TSG (if presented directly to TSG)
1. [ ] Work item code (from WI list)
1. [ ] Release (one only)
1. [ ] Category (TEI for technical enhancements)
1. [ ] Title (descriptive, not redundant)
1. [ ] Reason for change
1. [ ] Summary of changes
1. [ ] Consequences if not approved
1. [ ] Clauses affected (list individually)
1. [ ] Other specs affected
1. [ ] Other comments (optional)
1. [ ] Date (format: yyyy-MM-dd)
1. [ ] Release (Rel-4, Rel-5, etc.)
1. [ ] (U)SIM - ME/UE - Radio Access Network - Core Network checkboxes
1. [ ] UICC field (change to (U)SIM or ISIM)

### CR Revision History

Optional field in CR document to track changes as CR passes through revisions:

- Revision 1: Initial CR
- Revision 2: First revision of CR
- Revision 3: Subsequent revisions

### File Naming Convention

**Word™ files for CRs** follow 3GPP naming:

```
*<specnumber_no_dot>*_CR*<4-character_CR_number>*[r*<revision_number>*]
```

**Zip™ archive** containing CRs:

- Word™ files (CR cover sheet + body + attachments)
- Zip™ file named according to convention
- Contains multiple CRs packaged together for a TSG meeting

### CR Lifecycle

```
Draft → WG Agreement → TSG Approval → MCC Incorporation → Published Spec
```

## Change Request Workflow

### 1. Draft CR

Member organization creates CR document
↓

### 2. Submit to WG

WG discusses and agrees CR is valid
↓

### 3. WG Presents to TSG

WG presents CR at TSG plenary for approval
↓

### 4. TSG Approval

TSG approves CR (becomes decision)
↓

### 5. MCC Incorporates

MCC incorporates CR into new spec version
↓

### 6. Publish

New spec version becomes available

## Common Pitfalls

1. **Multiple Releases**: One spec may be maintained in multiple Releases
1. **Parallel CRs**: Need separate CRs for each Release with same WI code
1. **Editorial Changes**: Use "dot-one" versions, not full CRs
1. **Wrong Release**: Can't use Release 6 WI code for Release 4 spec
1. **Out-of-date Specs**: Writing CR to old version that's been updated

## Best Practices

1. **Always use WI codes** from official list
1. **Check spec version** before writing CR (is it in Release 4, Release 5, or current?)
1. **Target correct Release**: Each CR should target only one Release (unless mirror CR)
1. **Use proper categories**: TEI for technical enhancements, F for correctives
1. **Mirror CR requirements**: Include mirror CRs for all affected Releases if maintaining parallel versions
1. **Document revisions**: Use CR revision history field for tracking changes
1. **Format dates correctly**: Use `yyyy-MM-DD` format

## Cross-References

- **@3gpp-basics** - 3GPP organization and structure
- **@3gpp-working-groups** - Working Group responsibility for specs
- **@3gpp-tdocs** - CRs as meeting documents (tdocs)
- **@3gpp-releases** - Understanding Release structure
- **@3gpp-portal-authentication** - Some CR documents may require EOL access

## Resources

- 3GPP Official: <https://www.3gpp.org/>
- 3GPP Portal: <https://portal.3gpp.org/>
- Step-by-step: <https://www.3gpp.org/specifications-technologies/specifications-by-series/change-requests-step-by-step>
- CR Database: /ftp/Information/Databases/Change_Request/
- WI List: <https://www.3gpp.org/ftp/Specs/html-info/WI-List.htm>
- Netovate: <http://netovate.com/cr-search/>
