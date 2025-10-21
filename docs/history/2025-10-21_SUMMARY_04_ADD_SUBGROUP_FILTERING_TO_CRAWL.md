# Add Subgroup Filtering to `crawl` Command

**Date:** October 21, 2025

## Summary

Added the missing `--sub-group` / `-s` option to the `crawl` command to enable filtering TDocs by sub-working groups (e.g., SA4, RAN1, CT Plenary).

## Changes Made

### 1. CLI Update (`src/tdoc_crawler/cli.py`)

**Added parameter to `crawl` command:**
```python
subgroup: list[str] | None = typer.Option(None, "--sub-group", "-s", help="Filter by sub-working group")
```

**Updated config instantiation:**
```python
subgroups = _parse_subgroups(subgroup)  # Parse and normalize aliases
config = TDocCrawlConfig(
    # ...
    subgroups=subgroups,  # Pass to config
    # ...
)
```

### 2. Crawler Logic (`src/tdoc_crawler/crawlers/tdocs.py`)

**Improved `_extract_subgroup` method:**
- Now returns **codes** (R1, S4, RP) instead of full names (RAN1, SA4, RAN Plenary)
- Properly extracts subgroup from FTP directory names:
  - `TSG_RAN` → `RP` (RAN Plenary)
  - `WG4_Codec` → `S4` (SA4)
  - `WG1_RL1` → `R1` (RAN1)

**Added filtering logic in `_process_file`:**
```python
# Filter by subgroups if specified
if config.subgroups is not None and subgroup is not None:
    normalized_subgroup = subgroup.upper().strip()
    if not any(normalized_subgroup == sg.upper().strip() for sg in config.subgroups):
        return  # Skip this TDoc
```

### 3. Test Updates (`tests/test_crawler.py`)

Updated `test_extract_subgroup` to verify correct code extraction:
- `TSG_RAN` → `RP` ✓
- `WG1_RL1` → `R1` ✓
- `WG4_Codec` → `S4` ✓

## Usage Examples

### Filter by specific subgroup
```bash
# Crawl only SA4 TDocs
tdoc-crawler crawl -s S4

# Crawl only RAN1 and RAN2 TDocs
tdoc-crawler crawl -s R1 -s R2

# Crawl only RAN Plenary TDocs
tdoc-crawler crawl -s RP
```

### Filter by working group and subgroup
```bash
# Crawl SA4 TDocs (explicit working group)
tdoc-crawler crawl -w SA -s S4

# Crawl multiple subgroups within SA
tdoc-crawler crawl -w SA -s S1 -s S2 -s S4
```

### Subgroup without working group
The `-s` option works **without** explicit `-w` specification. The crawler:
1. Normalizes the subgroup alias (S4 → S4, RP → RP)
2. Walks all working groups' FTP directories
3. Filters TDocs based on extracted subgroup codes

Example:
```bash
# This works - crawls only S4 TDocs from SA working group
tdoc-crawler crawl -s S4
```

## Supported Aliases

All aliases from `MEETING_CODE_REGISTRY` are supported:

**RAN:**
- `RP` - RAN Plenary
- `R1` - RAN1
- `R2` - RAN2
- `R3` - RAN3
- `R4` - RAN4
- `R5` - RAN5
- `R6` - RAN6

**SA:**
- `SP` - SA Plenary
- `S1` - SA1
- `S2` - SA2
- `S3` - SA3
- `S4` - SA4
- `S5` - SA5
- `S6` - SA6

**CT:**
- `CP` - CT Plenary
- `C1` - CT1
- `C2` - CT2
- `C3` - CT3
- `C4` - CT4
- `C5` - CT5
- `C6` - CT6

## Technical Details

### FTP Directory Mapping

The crawler maps FTP directory names to subgroup codes:

| FTP Directory Pattern | Subgroup Code | Example |
|-----------------------|---------------|---------|
| `TSG_<WG>` | `<W>P` | `TSG_RAN` → `RP` |
| `WG<n>_<name>` | `<W><n>` | `WG4_Codec` → `S4` |

Where `<W>` is the first letter of the working group (R, S, or C).

### Filtering Algorithm

1. User specifies: `-s S4`
2. `_parse_subgroups()` normalizes to `["S4"]`
3. For each TDoc file found:
   - Extract subgroup code from FTP path
   - Compare (case-insensitive): `S4` == `S4` ?
   - If match: collect TDoc
   - If no match: skip TDoc

## Testing

All existing tests pass:
- ✅ `test_extract_subgroup` - Verifies code extraction from FTP paths
- ✅ `test_crawl_collects_tdocs` - Verifies basic crawl functionality
- ✅ Manual verification with `tdoc-crawler crawl -s S4 --help`

## Implementation Notes

1. **Consistency:** Subgroup filtering works the same way in both `crawl` and `query-meetings` commands
2. **Case-insensitive:** Comparisons use `.upper()` for robustness
3. **Multiple subgroups:** Users can specify `-s` multiple times
4. **No validation errors:** Invalid subgroup codes are passed through (crawler simply won't find matching TDocs)

## Related Commands

For reference, these commands already supported subgroup filtering:
- `query-meetings -s <subgroup>` - Query meeting metadata by subgroup
- (Now) `crawl -s <subgroup>` - Crawl TDocs by subgroup ✓
