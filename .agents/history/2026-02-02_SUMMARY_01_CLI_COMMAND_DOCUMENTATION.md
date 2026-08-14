# Summary: CLI Command Documentation Update

**Date:** 2026-02-02
**Task:** tdc-1ye

## Overview

Updated `docs/QUICK_REFERENCE.md` with comprehensive documentation for all CLI commands, explaining their differences, typical use cases, and command relationships.

## Changes Made

### Documentation Enhancements

1. **Added Command Overview Section**

   - Introduced command categories (Crawling, Querying, Utilities)
   - Documented short aliases (`ct`, `cm`, `qt`, `qm`)
   - Added typical workflow guide (Initial Setup → Incremental Updates → Querying)

1. **Added Command Differences Section**

   - Created comparison table for `crawl-tdocs` vs `crawl-meetings`
   - Created comparison table for `query-tdocs` vs `query-meetings`
   - Explained execution order requirements
   - Documented data sources and credential requirements

1. **Enhanced `crawl-tdocs` Documentation**

   - Added "When to Use" section
   - Comprehensive options table with descriptions
   - Expanded examples with more use cases
   - Documented parallel worker configuration

1. **Enhanced `crawl-meetings` Documentation**

   - Added "When to Use" section
   - Comprehensive options table with descriptions
   - Documented ETSI Online credential usage
   - Added subgroup crawling examples

1. **Enhanced `query-tdocs` Documentation**

   - Added "When to Use" section
   - Documented automatic fetch behavior (targeted crawl)
   - Explained TDoc ID auto-inference from prefixes
   - Comprehensive options table

1. **Enhanced `query-meetings` Documentation**

   - Added "When to Use" section
   - Clarified no automatic fetch (vs query-tdocs)
   - Documented subgroup aliases table
   - Comprehensive options table

1. **Enhanced Utility Commands Documentation**

   - Added "When to Use" sections for `open`, `checkout`, `stats`
   - Documented behavior details for `open` command

1. **Restructured Document Organization**

   - Command Overview first (workflow, aliases, categories)
   - Detailed command documentation with comparison tables
   - Utility commands section
   - HTTP caching section moved to end (reference material)

## Technical Details

### Command Categories

| Category | Commands | Purpose |
|----------|----------|---------|
| Crawling | `crawl-tdocs`, `crawl-meetings` | Fetch metadata from 3GPP servers |
| Querying | `query-tdocs`, `query-meetings` | Search and display stored data |
| Utilities | `open`, `checkout`, `stats` | File access and inspection |

### Key Differences Documented

**`crawl-tdocs` vs `crawl-meetings`:**

- Data source (FTP vs Portal)
- Prerequisites (meetings DB required vs none)
- Execution order (after vs before)
- Credentials (none vs optional)

**`query-tdocs` vs `query-meetings`:**

- Returns (TDoc documents vs meeting schedules)
- Targeted fetch (automatic vs none)
- TDoc ID argument support (yes vs no)

## Files Modified

- `docs/QUICK_REFERENCE.md` - Comprehensive CLI documentation update

## Verification

- Document structure follows existing patterns
- Command names match actual CLI (`crawl-tdocs`, not `crawl`)
- Examples use correct syntax
- Tables properly formatted with markdown
- History file created at `docs/history/2026-02-02_SUMMARY_01_CLI_COMMAND_DOCUMENTATION.md`
