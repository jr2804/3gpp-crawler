______________________________________________________________________

## name: 3gpp-releases description: 3GPP release structure, versioning, TSG rounds, and release freeze concept. Use when understanding 3GPP release numbering, TSG round schedules, or finding specifications in releases. metadata: related: [3gpp-basics, 3gpp-working-groups, 3gpp-meetings, 3gpp-tdocs, 3gpp-portal-authentication, 3gpp-specifications, 3gpp-change-request]

# 3GPP Releases

**Official Release Timeline:** <https://www.3gpp.org/specifications-technologies/releases>

## Overview

3GPP specifications are published four times a year following quarterly Technical Specification Group (TSG) plenary meetings. Each Release represents a set of frozen technical specifications.

## Release Structure

### Release Numbering

3GPP uses a **version numbering scheme**:

- **Two-digit series number**: 21, 22, 23, etc. (indicates major technical version)
- **Three-digit spec number**: Incrementing within each series (e.g., 21.456, 21.457)
- **Complete format**: `21.456` (Series number + spec number)

**Examples:**

- Release 21: TS 21.456, 21.457, 21.458
- Release 22: TS 22.101, 22.102, 22.103
- Release 4: TS 4.001, TR 4.002

### Release Timeline

- **Rel-99**: 1999
- **Rel-4/5/6**: 2001-2006
- **Rel-7**: 2007 (LTE)
- **Rel-8/9/10**: 2009 (LTE-Advanced)
- **Rel-11/12/13/14**: 2011 (LTE-Advanced Pro)
- **Rel-15**: 2015 (LTE-Advanced Pro)
- **Rel-16/17/18**: 2017 (LTE-Advanced Pro + 5G features)
- **Rel-18**: 2019 (5G NR Standalone)
- **Rel-20**: Current release (4G/5G dual connectivity + 5G NR Standalone)

## TSG Rounds

### What is a TSG Round?

A TSG round is a quarterly plenary meeting where specifications are made available. Each TSG round produces:

1. **Newly under change control** specs (80%+ complete)
1. **Unchanged** specs from previous version
1. **Revised** specs incorporating approved Change Requests
1. **Upgraded** specs to current Release (at freeze time)

### TSG Round Schedule

**Four TSG plenaries per year:**

- March: RAN, SA, CT
- June: RAN, SA, CT
- September: RAN, SA, CT
- December: RAN, SA, CT

**Example 2025 Schedule:**

- March 2025: TSG RAN#107, TSG SA#107, TSG CT#107
- June 2025: TSG RAN#108, TSG SA#108, TSG CT#108
- September 2025: TSG RAN#109, TSG SA#109, TSG CT#109
- December 2025: TSG RAN#110, TSG SA#110, TSG CT#110

## Spec Availability

### FTP Directory Pattern

```
https://www.3gpp.org/ftp/Specs/<YYYY>-<MM>/
```

**TSG Round Examples:**

- RAN#110: `https://www.3gpp.org/ftp/Specs/2025-12/`
- SA#110: `https://www.3gpp.org/ftp/Specs/2025-12/SpecslistexTSG/TSG110.htm`
- CT#110: `https://www.3gpp.org/ftp/Specs/2025-12/SpecslistexTSG/TSG110.htm`

### Target Dates

- **MCC Target**: All new/revised specs available within 3 weeks after TSG plenary
- **Buffer Time**: Extra week added for large volumes or holiday periods

### Spec Types

- **TS (Technical Specification)**: Normative technical specifications
- **TR (Technical Report)**: Informative reports, studies

### Release Freeze

- **Definition**: Point after which only corrections are allowed
- **Backward Compatibility**: Major focus to ensure systems remain compatible
- **Forward Compatibility**: Building compatibility for future releases (e.g., NSA in early 5G NR)

## Closed Releases

Older releases that are "closed" - no further Change Requests accepted.

- **Examples:**
- Release 99: Closed
- Release 6: Closed
- Release 5: Closed
- Release 4: Closed

## Usage in Code

### Finding Specs by Release

```python
# FTP directory for Release 18
base_url = "https://www.3gpp.org/ftp/Specs/2018-12/"

# List all spec files
spec_list = requests.get(base_url).text.split('\n')
```

### Spec Number Pattern

TS numbers follow pattern: `<series>.<spec>`, where `<series>` is 21, 22, 23, etc.

**Examples:**

- TS 21.456: Series 21, spec 456
- TS 22.101: Series 22, spec 101
- TR 4.001: Series 4, spec 1 (Technical Report)

## Cross-References

- **@3gpp-working-groups** - For understanding which TSGs produce which specs
- **@3gpp-specifications** - For spec file format and numbering
- **@3gpp-change-request** - For modifications to specs in releases

## Resources

- **3GPP Official**: <https://www.3gpp.org/>
- **3GPP Portal**: <https://portal.3gpp.org/>
- **MCC Info**: Available in spec list tables

## Key Points

- **Parallel Development**: Multiple releases worked on simultaneously (Rel-4, Rel-5, etc.)
- **Current Release**: Release 20 is in active development
- **Backward Compatibility**: Core design principle across all releases
- **Closed Releases**: No further modifications accepted
