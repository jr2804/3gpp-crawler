# CLI Refactoring Beads Issue Dependencies

## Issue Dependencies (Recommended Execution Order)

The following beads issues have been created with the recommended dependencies to ensure proper execution order and avoid conflicts.

| Issue ID | Title | Priority | Dependencies | Status |
|-----------|-------|-----------|--------------|--------|
| `tdc-lst` | Refactor cli/fetching.py: Remove duplicate fetch_tdoc() | P2 | None | open |
| `tdc-oot` | Move normalize_portal_meeting_name() from cli/helpers.py to specs/normalization.py | P3 | None | open |
| `tdc-5uc` | Move resolve_meeting_id() from cli/helpers.py to database module | P3 | None | open |
| `tdc-6ts` | Move download_to_path() from cli/helpers.py to http_client.py | P3 | None | open |
| `tdc-n80` | Move prepare_tdoc_file() from cli/helpers.py to checkout.py | P3 | Depends on `tdc-6ts` | open |
| `tdc-72h` | Move database_path() from cli/helpers.py to database module | P4 | None | open |
| `tdc-lmu` | Update src/tdoc_crawler/cli/AGENTS.md with completed refactoring | P4 | Depends on all refactoring | open |
| `tdc-z37` | Run full test suite after CLI refactoring | P1 | Depends on all refactoring | open |

## Dependency Definitions

### Without Dependencies (Can start in parallel)

These issues can be worked on immediately as they don't depend on other tasks:

- `tdc-lst` - Remove duplicate fetch_tdoc()
- `tdc-oot` - Move normalize_portal_meeting_name()
- `tdc-5uc` - Move resolve_meeting_id()
- `tdc-6ts` - Move download_to_path()
- `tdc-72h` - Move database_path()

### With Dependencies

These issues must wait for their dependencies to complete:

- `tdc-n80` - Depends on `tdc-6ts` (download_to_path)
- `tdc-lmu` - Depends on all refactoring tasks (#1-#6)
- `tdc-z37` - Depends on all refactoring tasks (#1-#6)

## Manual Setup Instructions

The `bd` issue tracker's dependency flag syntax is:

```bash
bd create <title> --type <type> --priority <priority> --deps <dependencies>

# Example:
bd create "Move prepare_tdoc_file()" --type task --priority 3 --deps tdc-6ts
```

## Beads Command Reference

Create issue:

```bash
bd create <title> [flags]
```

Close issue:

```bash
bd close <id>
```

Add dependencies to existing issue:

```bash
bd deps add <id> <type>:<dependency-id>
```

## Recommended Work Queue

### Phase 1: Foundation (No dependencies)

1. `tdc-lst` - Fix fetch_tdoc duplication (15 min)
1. `tdc-oot` - Move normalize_portal_meeting_name (15 min)
1. `tdc-5uc` - Move resolve_meeting_id (30 min)
1. `tdc-6ts` - Move download_to_path (15 min)
1. `tdc-72h` - Move database_path (20 min)

### Phase 2: Integration (Depends on Phase 1)

6. `tdc-n80` - Move prepare_tdoc_file (30 min) - depends on `tdc-6ts`

### Phase 3: Documentation & Verification (Depends on all)

7. `tdc-lmu` - Update AGENTS.md (10 min)
1. `tdc-z37` - Run full test suite (10 min)

## Estimated Total Time: ~2.5 hours
