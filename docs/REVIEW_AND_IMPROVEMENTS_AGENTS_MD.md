# Review and Improvements for AGENTS.md

**Date**: 2025-10-22 (Addendum)
**Reviewer**: AI Assistant
**Purpose**: Update and extend earlier review to incorporate latest codebase refactoring (schema v2, modular CLI/database) and identify any remaining misalignments between `AGENTS.md` and current implementation.

---

## 1. Executive Summary

The previous review (earlier part of this file) highlighted missing documentation on HTTP crawling, subdirectory detection, fuzzy meeting name matching, and portal authentication. Those concerns have since been largely addressed inside `AGENTS.md` (the document now contains sections titled “HTTP Directory Crawling and File Detection” and subdirectory logic, plus portal module references). However, substantial new divergences have appeared after the recent refactor:

High‑impact mismatches:
1. Database schema in `AGENTS.md` describes an older (pre‑v2) table layout – omits columns now present and still lists non‑existent ones (e.g. `for_value`, `last_validated`, missing `url`, `file_size`, `for_purpose`, `document_type`, `checksum`, `source_path`, `date_updated`, `validation_failed`).
2. Project structure still assumes monolithic `cli.py` and `database.py` whereas code is now split (e.g. `src/tdoc_crawler/cli/app.py`, `cli/helpers.py`, `cli/fetching.py`, `cli/printing.py` and database submodules `database/schema.py`, `database/connection.py`, `database/tdocs.py`, `database/statistics.py`).
3. The removal of redundant columns (`working_group`, `subgroup`, `meeting`) from the `tdocs` table (schema v2) is not explicitly documented as a completed normalization step nor its consequences (JOIN-based derivation from `meetings`).
4. Testing guidance does not warn that foreign key integrity now requires inserting meetings before TDocs (was root cause for earlier failing tests).
5. Naming consistency: The live schema uses `for_purpose` but `AGENTS.md` still refers to `for_value`; this is a potential source of regenerated incorrect code.
6. Statistics and helper queries in current code derive working group counts via JOIN; `AGENTS.md` still suggests grouping directly on a removed column.
7. Crawl log structure changed (new fields: `crawl_type`, `start_time`, `end_time`, `incremental`, `items_added`, `items_updated`, `errors_count`, `status`), but the document lists an older minimal form (`timestamp`, `tdocs_discovered`, etc.).

If left uncorrected, a coding assistant following the existing `AGENTS.md` would regenerate obsolete schema, reintroduce denormalized columns, misname fields, and write incompatible queries/tests.

---

## 2. Recommended Structural Updates to AGENTS.md

| Area | Current Doc State | Required Update | Rationale |
|------|-------------------|-----------------|-----------|
| Project Structure | Single `cli.py`, `database.py` mentioned | Replace with granular module list (CLI and database subpackages) | Align with refactored modular design, aids navigation |
| Database Schema (TDocs) | Legacy column set | Provide complete schema v2 definition + highlight removed columns | Prevent regeneration of stale schema |
| Database Schema (Meetings/Subworking Groups) | Partially aligned | Add indices and schema_meta description | Document versioning & optimization |
| Crawl Log Table | Old minimal fields | Update to new expanded audit fields | Ensure logging features are represented |
| Normalization Rationale | Not explicit | Add subsection “Schema v2 Normalization Decisions” | Preserve architectural intent |
| Field Naming | Mixed (`for_value`) | Standardize on `for_purpose` | Consistency & correctness |
| Working Group Derivation | Implicit | Add explicit JOIN pattern description | Prevent reintroduction of removed columns |
| Statistics Queries | Assume `working_group` column exists | Show JOIN-based aggregation example | Match current implementation |
| Test Patterns | Missing FK insertion guidance | Add “Foreign Key Preparation” note | Avoid common test setup errors |
| Migration Guidance | Absent | Add minimal instructions for upgrading from schema v1→v2 | Helps future contributors |

---

## 3. Detailed Change Proposals

### 3.1 Project Structure Section
Replace the existing tree with:

```text
src/tdoc_crawler/
    cli/
        app.py          # Typer application & command registration
        fetching.py     # Targeted fetch & portal orchestration
        helpers.py      # Path/credentials resolution, fuzzy resolution helpers
        printing.py     # Output formatting (table/json/yaml/csv)
    crawlers/
        tdocs.py        # HTTP traversal, subdirectory detection, pattern filtering
        meetings.py     # Meeting list parsing & date extraction
        portal.py       # PortalSession authentication + metadata fetch
    database/
        schema.py       # SCHEMA_VERSION, table DDL, reference population
        connection.py   # TDocDatabase facade/context manager
        tdocs.py        # TDoc CRUD & query helpers (JOIN logic)
        statistics.py   # Aggregated reporting & crawl log queries
    models/           # Pydantic models & enums
    __init__.py
    __main__.py
```

Add an explicit note: “Monolithic `cli.py` and `database.py` referenced elsewhere are legacy; new contributions MUST use the modular structure above.”

### 3.2 Database Schema (v2) Correction

Present updated `tdocs` table (omit implementation code details, list columns logically):

```text
tdocs(
    tdoc_id TEXT PK COLLATE NOCASE,
    url TEXT NOT NULL,
    meeting_id INTEGER NOT NULL FK meetings(meeting_id),
    file_size INTEGER,
    title TEXT,
    contact TEXT,
    tdoc_type TEXT,
    for_purpose TEXT,
    agenda_item TEXT,
    status TEXT,
    is_revision_of TEXT FK tdocs(tdoc_id),
    document_type TEXT,
    checksum TEXT,
    source_path TEXT,
    date_created TEXT,
    date_retrieved TEXT NOT NULL,
    date_updated TEXT NOT NULL,
    validated INTEGER NOT NULL DEFAULT 0,
    validation_failed INTEGER NOT NULL DEFAULT 0
)
```

Add note: “Columns `working_group`, `subgroup`, `meeting` removed in v2 – derive via JOIN on `meetings`.”

### 3.3 Normalization Rationale Subsection

Add after schema: briefly enumerate benefits (reduced redundancy, consistent derivation, simplified updates, enforced FK integrity). Explicitly warn not to reintroduce denormalized columns.

### 3.4 Working Group Derivation Pattern

Add minimal guidance:

```sql
SELECT t.tdoc_id, wg.code AS working_group, sw.code AS subgroup
FROM tdocs t
JOIN meetings m ON t.meeting_id = m.meeting_id
JOIN working_groups wg ON m.tbid = wg.tbid
JOIN subworking_groups sw ON m.subtb = sw.subtb;
```

Clarify this replaces any former reliance on stored text columns.

### 3.5 Statistics Query Update

Replace grouping example using removed column with JOIN-based aggregation. Emphasize NOT to assume `working_group` column exists in `tdocs`.

### 3.6 Crawl Log Table Update

Document new fields: `crawl_type`, `start_time`, `end_time`, `working_groups` (serialized list), `incremental`, `items_added`, `items_updated`, `errors_count`, `status`, `created_at`. State purpose: audit, performance metrics, incremental tracking.

### 3.7 Field Naming Consistency

Global replacement instruction: Use `for_purpose` (deprecate `for_value`). Add a short mapping table for legacy → current names (avoid code snippets).

### 3.8 Test Guidance Enhancement

Add “Foreign Key Preparation” subsection:

- Always insert meeting rows before inserting TDocs referencing them.
- Fixtures should centralize meeting creation (e.g., helper akin to `insert_sample_meetings`).
- Negative tests: intentionally omit meeting to assert FK failure only when testing integrity.


### 3.9 Migration Guidance (Schema v1→v2)

Outline minimal steps:

1. Backup DB.
2. Create new schema (v2) in empty DB.
3. Copy `meetings`, `working_groups`, `subworking_groups`.
4. Transform old `tdocs` rows: drop redundant columns, map `for_value`→`for_purpose`, inject `date_updated` = `date_retrieved` if missing.
5. Recompute statistics/crawl log if structure changed.

Include warning: direct in-place ALTER sequence is more complex due to column removals; prefer rebuild + migrate.

### 3.10 Portal Authentication Clarification

Ensure AGENTS.md states: “Portal metadata fetch is optional for basic crawling; failures should mark `validation_failed=1` without halting batch.” Avoid implying hard stop behavior.

### 3.11 Consistency Pass Recommendations

Add brief editorial checklist for maintainers: verify schema version constant, confirm normalized queries, ensure no resurrected legacy column names, validate tests insert meetings first, confirm docs reflect current CLI module split.

---

## 4. Redundant / Outdated Content to Remove or Condense

| Section | Action |
|---------|--------|
| Any lingering ‘FTP crawling’ headings | Replace with ‘HTTP directory traversal’ |
| Old pattern examples using `^[RSTC]\d+-\d+` | Remove (use consolidated regex already present) |
| References to single-file `cli.py` implementing all commands | Update to modular CLI layout |
| Grouping examples over `working_group` column | Replace with JOIN-based examples |
| Outdated crawl_log schema (timestamp + counts) | Replace with expanded fields table |


---

## 5. Items Already Correct (No Change Needed)

These portions of `AGENTS.md` accurately reflect current design:

- TDoc filename regex and explanation (matches live implementation).
- Subdirectory detection concept (Docs/Documents variants) – ensure remains concise.
- Fuzzy meeting name matching principles (prefix/suffix strategy without substring matching).
- Credential resolution order (CLI args → env vars → prompt).


---

## 6. Risk Assessment if Not Updated

| Risk | Consequence |
|------|-------------|
| Regenerating legacy schema | Runtime errors, mismatched columns, failed inserts |
| Using old denormalized fields | Data inconsistency, duplicated update logic |
| Wrong field names (`for_value`) | Silent bugs when persisting or querying portal metadata |
| Missing FK setup in tests | High volume of failing tests, false negatives |
| Misleading project structure | Contributor confusion, bloated single-file rewrites |


---

## 7. Summary of Required Doc Changes (Action Checklist)

1. Update project structure tree → modular layout.
2. Replace TDocs table definition with v2 schema; add normalization rationale.
3. Add JOIN pattern for deriving working group/subgroup.
4. Update statistics aggregation section.
5. Document new crawl_log fields.
6. Standardize naming (`for_purpose`).
7. Add FK test preparation guidance.
8. Add migration guide v1→v2.
9. Clarify portal failure handling (non-fatal, mark `validation_failed`).
10. Insert consistency editorial checklist.


---

## 8. Final Recommendation
`AGENTS.md` should be revised to reflect schema v2 and modular architecture before further feature work. The changes are corrective (alignment with implemented code) rather than new feature proposals. Proceed with updating the document; no blocking concerns identified.

If implementers decide not to update immediately, at minimum pin a banner at top: “WARNING: Some sections are outdated for schema v2; consult `database/schema.py` and `cli/` submodules.”

---

## 9. If No Immediate Edits Are Possible
State plainly: regeneration attempts MUST read actual source modules for authoritative column lists; treat existing schema description in `AGENTS.md` as deprecated.

---

## 10. Conclusion
The current `AGENTS.md` is partially updated but still materially inconsistent with live code. Updating it per the checklist above will materially reduce regeneration errors and ensure assistants produce normalized, forward-compatible implementations.

---
End of addendum.

**Note**: Legacy content from earlier review iterations has been removed for clarity.
