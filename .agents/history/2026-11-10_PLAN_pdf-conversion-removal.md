# Remove PDF conversion (pdf-remote-converter + convert-lo)

Status: PREPARED, nothing executed. Gitignored working artifact.

## Goal and rationale

Project scope is offline tdoc handling and meetings/specs sync. Office-to-PDF
conversion existed only to feed knowledge/AI tooling. Newer tools (parsecraft,
docling, docling-rs) convert doc/docx themselves or use LibreOffice internally,
so the project keeps no conversion code of its own. Record in `.agents/HISTORY.md`.

## Findings (as of this plan)

- `convert-lo` is used only by `src/tdoc_crawler/extraction/convert.py`.
- `pdf-remote-converter` is imported only by `convert.py` (module level, lines 19-23).
- `--pdf` is wired into CLI (`cli/args.py:144-146` `PdfOption`, `cli/checkout.py:43,103-108`,
  `cli/specs.py:15,41,66-67`) and MCP (`mcp_server.py:182,189` `checkout_tdocs`, `:198,205` `checkout_specs`).
- `OFFICE_FORMATS` (defined in `convert.py:28`) is also used for main-file selection in
  `extraction/fetch_spec.py:16,149` — must move, not delete.
- `extraction/errors.py` `ConversionError` is used only by `convert.py`.
- `extraction/fetch_tdoc.py` `fetch_tdoc_files` and `fetch_spec.py` `fetch_spec_files` have no
  callers in `src/` outside `extraction/__init__.py`. Tests not yet checked.
- `packages/` workspace stays: `pool-executors` is also a member (`pyproject.toml:123` `members = ["packages/*"]`).
- `uv.lock` is gitignored (`.gitignore:214`), so no lock commit is needed; regenerate locally.

## Phase 1 — core code (`src/tdoc_crawler/`)

1. Delete `extraction/convert.py`.
2. Move `OFFICE_FORMATS` to a neutral module (decision pending, see Open questions); update
   `extraction/fetch_spec.py:16` import.
3. Update `extraction/__init__.py`: drop `ConverterConfig`, `convert_dir_to_pdf`, `convert_to_pdf`,
   `ensure_pdf` re-exports and their `__all__` entries (lines 8-15, 25-30). Keep `fetch_*` unless decided.
4. Delete `extraction/errors.py` if `ConversionError` has no other user (verify with grep before deleting).
5. CLI: remove `PdfOption` (`cli/args.py:144-146`); remove `pdf` param, import, and the
   `if pdf:` block in `cli/checkout.py` (lines 20, 27, 43, 103-108) and `cli/specs.py`
   (lines 15, 25, 41, 66-67 and its print lines).
6. MCP: remove `pdf` param and `pdf=pdf` passthrough in `mcp_server.py` lines 182, 189, 198, 205.
   This changes MCP tool signatures (breaking for agents passing `pdf`).
7. `tdocs/operations/checkout.py:32-35` comment refers to `OFFICE_FORMATS` in `convert.py`; rewrite comment.
   Keep `_TDOC_DOCUMENT_SUFFIXES` (still needed for main-file ranking).
8. Check `extraction/fetch_tdoc.py` cycle note in `src/tdoc_crawler/AGENTS.md:106` after the move.

## Phase 2 — packaging

1. `pyproject.toml`: remove line 20 `"convert-lo"`, line 40 `"pdf-remote-converter"`,
   line 126 `convert-lo = { workspace = true }`, line 130 `pdf-remote-converter = { git = ... }`.
   Keep line 123 `members = ["packages/*"]` and `pool-executors` source (line 127).
2. Delete `packages/convert-lo/` (AGENTS.md, LICENSE, README.md, pyproject.toml, `convert_lo/`).
3. Delete `tests/convert_lo/` (conftest, test_converter, test_formats, test_hybrid_converter,
   test_integration, test_locator, examples/).
4. Regenerate local lock/env: `uv lock` then `uv sync --all-packages`. Confirm
   `pdf-remote-converter` and `convert-lo` are gone from resolution.
5. Check `deptry` / `pydeps` config if any references remain (none found in `pyproject.toml`).

## Phase 3 — docs and config

1. Delete `docs/convert-lo-usage.md`; remove nav entries `mkdocs.yml:23` and `zensical.toml:24`.
2. `docs/utils.md:19-25, 48, 52`: remove `--pdf` text and examples.
3. `README.md:20` (PDF Conversion bullet), `:107`, `:113` (remove "use `--pdf`" parentheticals).
4. `.env.example:107-126` (pdf-remote-converter block) and provider blocks at `:128-148`
   (CloudConvert, Adobe, Zamzar). Read the full block before editing.
5. `skills/3gpp-crawler/SKILL.md` lines 3 (description mentions PDF conversion), 19, 27, 48-49,
   86, 89, 101 (`--pdf` lines and LibreOffice/remote note). `skills/3gpp-crawler/references/cli-quick-ref.md`
   lines 57, 97, 138-139.
6. `src/tdoc_crawler/cli/AGENTS.md:67` (`PDF_ONLY` / `ensure_pdf()` line): delete.
7. `src/tdoc_crawler/AGENTS.md:106` (OFFICE_FORMATS mention) and `:112` (`--pdf` rationale for clutter
   filter): rewrite. Clutter filter stays at the extraction boundary, but the stated reason changes.
8. Root `AGENTS.md:102`: delete `packages/convert-lo/AGENTS.md` row from Child DOX Index.
9. `.agents/HISTORY.md`: add one row recording the removal decision and rationale.
10. Do NOT edit `.agents/history/*` (archived records; mentions stay).
11. `.agents/FILES.md` and `.agents/TOOLS.md`: no current convert-lo/pdf rows found; re-check after edits.

## Phase 4 — verification

1. Sanity grep (exclude `.agents/history/`):
   `convert_lo|convert-lo|pdf_remote|pdf-remote|PDF_REMOTE|ensure_pdf|convert_dir_to_pdf|convert_to_pdf|PdfOption|ConversionError|soffice|LIBREOFFICE|--pdf`.
2. `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`.
3. `uv run pytest` (baseline failures must be stated, not attributed to this change).
4. `mise run docs` (= `uv run mkdocs build --strict`).
5. `uv run python -c "import tdoc_crawler.cli.tdoc_app, tdoc_crawler.mcp_server"` to confirm the
   package imports without pdf-remote-converter or convert_lo.
6. CLI smoke: `uv run tdoc-crawler checkout --help` shows no `--pdf`.

## Phase 5 — release and history

- Commit only on explicit request (POLICIES). Commit message must state the removal and why.
- CLI flag and MCP parameter removals are breaking; note in commit and HISTORY.
- Existing PDFs already written into checkout directories are user data; do not delete them.
- The pre-commit hook bumps CalVer on main commits; expected.
- Archive this plan to `.agents/history/<date>_PLAN_remove_pdf_conversion.md` after landing
  (completion-date prefix per FILES.md naming). Plan folder is gitignored.

## Open questions (need user decision before Phase 1)

1. Where should `OFFICE_FORMATS` live? Options: `constants/` module, or inside `fetch_spec.py`.
2. Delete the whole `extraction/` package (incl. `fetch_tdoc.py`, `fetch_spec.py`) if they are dead
   code, or keep it as the home for file-fetch helpers? Needs a test-usage check first.
3. Accept the breaking MCP tool signature change (`checkout_tdocs`/`checkout_specs` lose `pdf`)?
4. Update `skills/3gpp-crawler/` docs in the same change, or separately?
