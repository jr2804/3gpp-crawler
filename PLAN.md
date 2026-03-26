# PLAN: Structured Extraction Artifact Storage

**Feature:** Store extracted tables, figures, equations in organized `.ai` subfolders with temp-then-commit pattern

**Created:** 2026-03-26 00:30

---

## Quality Guidelines (Phase 0)

**MUST follow for all implementation work:**

| Tool/Skill | Use For | When |
|------------|---------|------|
| `CytoScnPy` MCP server | Static analysis (unused code, complexity, security) | Before committing code |
| `debugging-code` skill + `dab` CLI | Interactive debugging (step-through, breakpoints, inspect state) | Instead of guessing/printing |
| `grepai` MCP server | Find similar code, methods, existing functionality | Before writing new code |
| `test-driven-development` skill | Writing tests first, red-green-refactor | All new functionality |
| `python-pro` skill | Modern Python 3.12+ patterns, async | Implementation |
| `python-standards` skill | Code quality, type hints, linting | All Python code |
| `python-testing-patterns` skill | pytest fixtures, mocking, isolation | Tests |
| `stop-slop` skill | Remove AI writing patterns from prose | Documentation/comments |
| `code-deduplication` skill | Prevent duplicate code semantically | Before adding new code |
| `visual-explainer` skill | Generate flowcharts/diagrams | Documentation |

**Rule:** Use debugging tools instead of print-statements or guessing. Use grepai to find existing patterns before implementing new ones.

---

## Quality Gates (Per Phase)

Every phase MUST pass these gates before moving to the next:

1. **Lint:** `ruff check packages/3gpp-ai/`
2. **Type check:** `ruff check packages/3gpp-ai/ --select=ANN`
3. **Tests:** `uv run pytest tests/ai/ -v`
4. **Static analysis:** `cytoscnpy analyze-path packages/3gpp-ai/`

If any gate fails, fix before proceeding.

---

## Goal

Refactor extraction artifact storage in both `process` and `convert_md` flows so that:

1. Tables, figures, equations are stored as individual files in `.ai/{tables,figures,equations}/` subfolders
2. Extraction uses a temp folder during processing; artifacts are moved on success
3. Re-extraction is skipped per-artifact-type if the corresponding subfolder already contains data
4. Both flows (`process` command and `convert_md`) share the same storage logic

---

## Context

### Current Storage Patterns

| Flow | File | Storage Location |
|------|------|------------------|
| `convert_md` | markdown | `.ai/{doc_id}.md` |
| `convert_md` | figures bytes | `.ai/figures/figure_N.png` |
| `convert_md` | tables | `.ai/{doc_id}_tables.json` (JSON sidecar) |
| `convert_md` | figures metadata | `.ai/{doc_id}_figures.json` (JSON sidecar) |
| `convert_md` | equations | `.ai/{doc_id}_equations.json` (JSON sidecar) |
| `process` | markdown | `.ai/{stem}.md` |
| `process` | figures bytes | `.ai/figures/figure_N.png` |
| `process` | tables | ❌ NOT stored |
| `process` | equations | ❌ NOT stored |

### Key Files

| File | Role |
|------|------|
| `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py` | Utilities: `persist_figures_from_kreuzberg_result()`, `from_kreuzberg_result()`, `build_structured_extraction_result()` |
| `packages/3gpp-ai/threegpp_ai/operations/convert.py` | `extract_tdoc_structured()`, `_write_structured_sidecars()`, `_read_cached_structured()`, `_build_structured_from_result()` |
| `packages/3gpp-ai/threegpp_ai/lightrag/processor.py` | `TDocProcessor.extract_text()` - main extraction for `process` command |

### Dependencies

- `kreuzberg` for extraction
- `convert-lo` for PDF conversion
- Existing `ExtractedTableElement`, `ExtractedFigureElement`, `ExtractedEquationElement` models

---

## Phases

### Phase 1: Define Artifact Storage Utilities

**File:** `packages/3gpp-ai/threegpp_ai/operations/extraction_result.py`

**Deliverables:**
- Add `ArtifactStorage` class or module-level functions for:
  - `persist_tables_from_extraction(tables: list[ExtractedTableElement], ai_dir: Path, doc_stem: str) -> list[Path]`
  - `persist_equations_from_extraction(equations: list[ExtractedEquationElement], ai_dir: Path, doc_stem: str) -> list[Path]`
  - `read_cached_artifacts(ai_dir: Path, doc_stem: str) -> StructuredExtractionResult`
  - `has_cached_artifacts(ai_dir: Path, doc_stem: str, artifact_types: set[str]) -> bool`
- Use temp folder pattern: write to `.{artifact_type}.tmp`, then atomic move on success
- Naming: `{doc_stem}_{type}_{page}_{index}.json` (e.g., `S4-250638_table_5_1.json`)
- Figure bytes: `{doc_stem}_figure_{page}_{index}.png`
- Unit tests in `tests/ai/test_extraction_result.py` (or extend existing tests)

**Validation:**
```bash
cd /path/to/3gpp-crawler
python -c "from threegpp_ai.operations.extraction_result import ArtifactStorage; print('ArtifactStorage imported')"
uv run pytest tests/ai/test_extraction_result.py -v
```

---

### Phase 2: Refactor `convert.py` to Use Folder Storage

**File:** `packages/3gpp-ai/threegpp_ai/operations/convert.py`

**Deliverables:**
- Modify `extract_tdoc_structured()` to:
  - Check for existing artifact folders before extraction
  - Call new storage functions instead of `_write_structured_sidecars()`
  - Use temp-then-commit pattern
- Replace `_write_structured_sidecars()` with calls to new `ArtifactStorage` functions
- Update `_read_cached_structured()` to read from folder structure
- No backward migration - old sidecars ignored, re-generated if needed
- Extend `tests/ai/test_operations_metrics.py` if it exists, or add tests for conversion

**Validation:**
```bash
cd /path/to/3gpp-crawler
uv run python -c "
from threegpp_ai.operations.convert import extract_tdoc_structured
from pathlib import Path
# Test with a known TDoc that has tables
# extraction = extract_tdoc_structured('S4-250638')
# assert (ai_dir / 'tables').exists()
print('convert.py validation passed')
"
uv run pytest tests/ai/ -v -k "convert or conversion"
```

---

### Phase 3: Refactor `processor.py` to Use Structured Storage

**File:** `packages/3gpp-ai/threegpp_ai/lightrag/processor.py`

**Deliverables:**
- Modify `TDocProcessor.extract_text()` to:
  - Check for existing `.ai/{stem}_tables/` folder to skip table extraction
  - Check for existing `.ai/{stem}_equations/` folder to skip equation extraction
  - Persist tables and equations using new storage utilities
  - Store figure metadata alongside figure bytes (not just sidecar)
- Align with `convert.py` storage pattern
- Add/update tests in `tests/ai/test_lightrag_processor.py` or similar

**Validation:**
```bash
cd /path/to/3gpp-crawler
uv run pytest tests/ai/test_lightrag_processor.py -v
# If test file doesn't exist, run: uv run pytest tests/ai/ -v -k "processor or extraction"
```

---

### Phase 4: Add Skip Logic for Re-extraction

**Files:** Both `convert.py` and `processor.py`

**Deliverables:**
- Extraction functions accept `extract_types: set[str]` parameter (e.g., `{"tables", "figures", "equations"}`)
- Skip extraction for types whose subfolders already contain artifacts
- `force=True` bypasses skip logic and re-extracts everything

**Validation:**
```bash
cd /path/to/3gpp-crawler
# Run process twice on same doc - second run should skip extraction
uv run tdoc-crawler ai workspace process -w test-skip
# Check logs show "Skipping X extraction - artifacts exist"
```

---

### Phase 5: Integration Test

**Files:** N/A (end-to-end validation)

**Deliverables:**
- Create integration test that:
  1. Creates a temporary workspace
  2. Adds a TDoc with known tables/figures/equations
  3. Runs `process` command
  4. Verifies all artifact folders contain expected files
  5. Runs `process` again - verifies skip logic works
  6. Cleans up workspace
- Or manual validation with real TDoc

**Validation:**
```bash
cd /path/to/3gpp-crawler
# Manual test:
uv run tdoc-crawler ai workspace create test-integration --no-activate
uv run tdoc-crawler ai workspace add-members -w test-integration --kind tdoc S4-250638
uv run tdoc-crawler ai workspace process -w test-integration
# Verify .ai/{tables,figures,equations}/ folders exist and contain files
```

---

## Storage Structure (Target)

```
.ai/
  {doc_id}.md                           # Main markdown content
  {doc_id}.pdf                          # Converted PDF (office formats)
  
  tables/
    {doc_id}_table_{page}_{index}.json
    ...
    
  figures/
    {doc_id}_figure_{page}_{index}.png
    {doc_id}_figure_{page}_{index}.json  # Figure metadata
    ...
    
  equations/
    {doc_id}_equation_{page}_{index}.json
    ...
```

### File Formats

**Table JSON** (`{doc_id}_table_{page}_{index}.json`):
```json
{
  "element_id": "table_1",
  "page_number": 5,
  "row_count": 3,
  "column_count": 4,
  "cells": [["A1", "B1"], ["A2", "B2"]],
  "markdown": "| A1 | B1 |...",
  "caption": "Table caption if available"
}
```

**Equation JSON** (`{doc_id}_equation_{page}_{index}.json`):
```json
{
  "element_id": "equation_1",
  "page_number": 3,
  "latex": "E = mc^2",
  "raw_text": "E = mc^2"
}
```

**Figure JSON** (`{doc_id}_figure_{page}_{index}.json`):
```json
{
  "element_id": "figure_1",
  "page_number": 7,
  "image_path": "S4-250638_figure_7_1.png",
  "image_format": "png",
  "caption": "Figure caption",
  "description": "Vision-LLM description if available",
  "metadata": {}
}
```

---

## Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Folder structure over JSON sidecars | Easier to inspect/debug, individual file access | ✅ Decided |
| Temp-then-commit pattern | Avoids incomplete artifact sets on failure | ✅ Decided |
| Per-type skip logic | Allows selective re-extraction | ✅ Decided |
| Backward compatibility with old sidecars | No migration - re-generation is fine | ✅ Decided |
| Filename must link to document location | Page number in filename or as first-class field | ✅ Decided |

---

## Artifact Naming Convention

Filenames MUST enable clear assignment back to the source document location (especially page number).

**Pattern:** `{doc_id}_{type}_{page}_{index}.json`

| Artifact | Filename Pattern | Example |
|----------|-----------------|---------|
| Table | `{doc_id}_table_{page}_{index}.json` | `S4-250638_table_5_1.json` |
| Equation | `{doc_id}_equation_{page}_{index}.json` | `S4-250638_equation_3_1.json` |
| Figure | `{doc_id}_figure_{page}_{index}.json` | `S4-250638_figure_7_1.json` |

**Rationale:** Page number in filename allows correlating artifact to source without parsing JSON.

---

## Notes

- Temp-then-commit: use `tempfile.mkdtemp()` for temp extraction, then `shutil.movetree()` to target folder
- Ensure `pathlib.Path` operations are used (no `os.path`)
- If extraction fails mid-way, temp folder is cleaned up automatically
- On success, move temp folder contents to final location atomically where possible

---

## Progress

- [x] (2026-03-26 00:30) Created PLAN.md
- [x] Phase 0: Quality gates defined
- [x] Phase 1: Implement ArtifactStorage utilities (extraction_result.py)
- [x] Phase 2: Refactor convert.py to folder storage
- [x] Phase 3: Refactor processor.py to folder storage
- [x] Phase 4: Add skip logic for re-extraction (extract_types parameter)
- [x] Phase 5: Integration test / end-to-end validation (`tests/ai/test_ai_extraction_artifacts.py`, 10/10 passing)
