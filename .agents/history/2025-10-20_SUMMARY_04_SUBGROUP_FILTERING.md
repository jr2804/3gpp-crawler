# Summary: Subgroup Filtering and Alias Support

**Date:** 2025-01-20
**Type:** Feature Enhancement

## Overview

Added comprehensive subgroup filtering support to the `query-meetings` command with full alias support for both working groups and subgroups. Users can now filter meetings by specific subgroups (e.g., SA4, RAN1) using either canonical names or short aliases.

## Changes Made

### 1. Database Layer (`src/tdoc_crawler/database.py`)

**Updated `TDocDatabase.query_meetings()`:**

- Added subgroup filtering logic to SQL WHERE clause
- Uses case-insensitive comparison: `UPPER(subgroup) IN (...)`
- Properly handles `None` case (no filtering when subgroups parameter is None)

```python
if config.subgroups:
    # Use UPPER() for case-insensitive comparison
    placeholders = ",".join(["?"] * len(config.subgroups))
    clauses.append(f"UPPER(subgroup) IN ({placeholders})")
    params.extend([sg.upper() for sg in config.subgroups])
```

### 2. Data Models (`src/tdoc_crawler/models.py`)

**Updated `MeetingQueryConfig`:**

- Added `subgroups: list[str] | None` field with description
- Added `@field_validator` that normalizes subgroups (uppercase, strip whitespace)
- Ensures consistent format regardless of user input casing

```python
class MeetingQueryConfig(BaseConfigModel):
    subgroups: list[str] | None = Field(None, description="Filter by sub-working group")

    @field_validator("subgroups", mode="before")
    def _normalize_subgroups(cls, value):
        if value is None:
            return None
        return [item.upper().strip() for item in value]
```

### 3. Crawler Utilities (`src/tdoc_crawler/crawler.py`)

**Added `normalize_working_group_alias()` function:**

- Maps plenary aliases to canonical names: RP↔RAN, SP↔SA, CP↔CT
- Returns normalized working group name
- Used in CLI parsing for `-w`/`--working-group` parameter

**Added `normalize_subgroup_alias()` function:**

- Returns list of canonical subgroup names matching the alias
- Searches through `MEETING_CODE_REGISTRY` for code matches
- Handles both short codes (S4, R1, RP) and long names (SA4, RAN1, RAN Plenary)
- Returns empty list if no match found

```python
def normalize_subgroup_alias(alias: str) -> list[str]:
    """Returns list of canonical subgroup names matching the alias."""
    normalized = alias.upper().strip()
    results = []
    for _working_group, entries in MEETING_CODE_REGISTRY.items():
        for code, subgroup in entries:
            if code == normalized or subgroup.upper() == normalized:
                if subgroup not in results:
                    results.append(subgroup)
    return results
```

### 4. CLI Layer (`src/tdoc_crawler/cli.py`)

**Updated `query_meetings()` command:**

- Added `subgroup` parameter: `--sub-group`/`-s` (supports multiple values)
- Added `_parse_subgroups()` helper function that:
  - Returns `None` if no subgroups specified
  - Calls `normalize_subgroup_alias()` for each input value
  - Expands aliases to canonical names
  - Removes duplicates while preserving order
  - Exits with error if unknown subgroup provided

**Enhanced `_parse_working_groups()` function:**

- Now calls `normalize_working_group_alias()` for alias expansion
- Supports plenary aliases: RP→RAN, SP→SA, CP→CT

```python
def _parse_subgroups(values: list[str] | None) -> list[str] | None:
    """Parse and normalize subgroup names, expanding aliases to canonical names."""
    from tdoc_crawler.crawler import normalize_subgroup_alias

    if not values:
        return None

    resolved: list[str] = []
    for item in values:
        normalized = normalize_subgroup_alias(item)
        if not normalized:
            console.print(f"[red]Unknown subgroup: {item}")
            raise typer.Exit(code=2)
        resolved.extend(normalized)

    # Remove duplicates while preserving order
    seen = set()
    unique_resolved = []
    for name in resolved:
        if name not in seen:
            seen.add(name)
            unique_resolved.append(name)

    return unique_resolved if unique_resolved else None
```

### 5. Tests (`tests/test_cli.py`)

**Added comprehensive test coverage:**

- `test_query_meetings_with_subgroup_filter`: Tests direct subgroup filtering
- `test_query_meetings_with_subgroup_alias`: Tests S4→SA4 alias expansion
- `test_query_meetings_with_plenary_alias`: Tests RP→RAN PLENARY alias expansion
- `test_query_meetings_with_working_group_alias`: Tests SP→SA alias for working groups
- `test_query_meetings_combined_filters`: Tests combined `-w SA -s S4` filtering

All tests use mocks to verify correct parameter passing without requiring full database.

## Supported Aliases

### Working Group Aliases (for `-w` parameter)

- `RP` → `RAN` (RAN Plenary)
- `SP` → `SA` (SA Plenary)
- `CP` → `CT` (CT Plenary)

### Subgroup Aliases (for `-s` parameter)

**SA Subgroups:**

- `S1` → `SA1`
- `S2` → `SA2`
- `S3` → `SA3`
- `S4` → `SA4`
- `S5` → `SA5`
- `S6` → `SA6`
- `SP` → `SA Plenary`

**RAN Subgroups:**

- `R1` → `RAN1`
- `R2` → `RAN2`
- `R3` → `RAN3`
- `R4` → `RAN4`
- `R5` → `RAN5`
- `R6` → `RAN6`
- `RP` → `RAN Plenary`

**CT Subgroups:**

- `C1` → `CT1`
- `C2` → `CT2`
- `C3` → `CT3`
- `C4` → `CT4`
- `C5` → `CT5`
- `C6` → `CT6`
- `CP` → `CT Plenary`

## Usage Examples

### Basic subgroup filtering

```bash
uv run tdoc-crawler query-meetings -w SA -s SA4 --limit 5
```

### Using short alias

```bash
uv run tdoc-crawler query-meetings -w SA -s S4 --limit 5
```

### Filtering plenary meetings

```bash
uv run tdoc-crawler query-meetings -w RP -s "RAN Plenary" --limit 5
```

### Using working group alias

```bash
uv run tdoc-crawler query-meetings -w SP --limit 5
```

### Multiple subgroups

```bash
uv run tdoc-crawler query-meetings -w RAN -s R1 -s R2 --limit 10
```

### Combined filters with aliases

```bash
uv run tdoc-crawler query-meetings -w SP -s S4 --limit 5
```

## Test Results

All tests passing (62/62):

- ✓ 17 CLI tests (including 5 new tests for subgroup filtering)
- ✓ 10 Crawler tests
- ✓ 14 Database tests
- ✓ 11 Model tests
- ✓ 10 Targeted fetch tests

## Implementation Notes

1. **Case Insensitivity**: Both database queries and user input are case-insensitive
1. **Alias Resolution**: Happens at CLI layer before passing to data models
1. **Validation**: Model validators ensure consistent uppercase format
1. **Deduplication**: Multiple aliases resolving to same subgroup are deduplicated
1. **Error Handling**: Clear error messages for unknown subgroups/working groups
1. **Backward Compatibility**: Existing functionality unchanged; new parameters are optional

## Files Modified

1. `src/tdoc_crawler/database.py` - Added subgroup filtering to query
1. `src/tdoc_crawler/models.py` - Added subgroups field to MeetingQueryConfig
1. `src/tdoc_crawler/crawler.py` - Added alias normalization functions
1. `src/tdoc_crawler/cli.py` - Added CLI parameters and parsing functions
1. `tests/test_cli.py` - Added comprehensive test coverage
