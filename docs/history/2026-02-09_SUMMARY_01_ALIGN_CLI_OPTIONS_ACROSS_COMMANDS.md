# Summary - Align CLI options across query/crawl commands (tdc-dxd)

Aligned `--clear-tdocs`, `--clear-specs`, and `--checkout` options across all query and crawl commands in the CLI to provide a consistent user experience and more granular data management.

## Changes

### CLI Layer

- **New Options**: Added `--clear-tdocs`, `--clear-specs`, and `--checkout` to `crawl-tdocs`, `crawl-meetings`, `crawl-specs`, `query-tdocs`, `query-meetings`, and `query-specs`.
- **Granular Clearing**:
  - `crawl-meetings` now supports `--clear-db` (everything), `--clear-tdocs` (only tdocs), and `--clear-specs` (only specs).
  - `crawl-tdocs` and `crawl-specs` support their respective clear flags.
  - All query commands now support clearing data before execution if requested.
- **Checkout Integration**: All crawl/query commands now support a `--checkout` flag that automatically downloads and extracts results to the `checkout` directory after the main operation.
- **Helper Functions**:
  - `_clear_checkout_tdocs`: Clears TDoc files from the checkout directory while preserving specifications.
  - `_clear_checkout_specs`: Clears specification files from the checkout directory.
  - `_checkout_tdocs`, `_checkout_specs`, `_checkout_meeting_tdocs`: Standardized helper functions for batch checkout operations.

### Database Layer

- **`TDocDatabase`**:
  - Added `clear_specs()` method to selectively clear spec-related tables (`specs`, `spec_versions`, `spec_source_records`, `spec_downloads`).
  - Ensured `clear_tdocs()` and `clear_meetings()` are available for granular clearing.

### Models and Protocols

- **`SpecQueryResult`**: Added `source_differences` field to store metadata discrepancies between sources.
- **`SpecSource`**: Updated protocol to use `@property` for `name`.
- **`SpecQueryFilters`**: Added `SpecQueryFilters` dataclass for structured spec querying.

### Bug Fixes

- Fixed `NameError: name 'field' is not defined` in `src/tdoc_crawler/models/specs.py`.
- Corrected type hints in `src/tdoc_crawler/cli/args.py` using `TypeAlias`.

## Verification Results

- All existing tests passed (217 passed).
- Manual audit confirmed all query/crawl commands in `app.py` implement the new options.
- Documentation in `QUICK_REFERENCE.md` updated to reflect the new CLI structure.
