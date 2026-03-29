# Phase 4: Documentation & Tooling - Context

**Phase:** 4 of 4  
**Created:** 2026-03-30  
**Status:** DISCUSSED

## Phase Requirements (from REQUIREMENTS.md)

### Documentation & Tooling

| ID | Description |
|----|-------------|
| DOCS-01 | Auto-generate config documentation from pydantic models |
| DOCS-02 | Add `config validate` CLI command to check config files |
| DOCS-03 | Updated `.env.example` with all supported variables |
| DOCS-04 | Migration guide for users with existing `.env` files |

### Alignment

| ID | Description |
|----|-------------|
| ALIGN-01 | 3gpp-ai package config references main crawler (no duplication) |
| ALIGN-02 | Consistent naming convention across packages |
| ALIGN-03 | Single source of truth for shared settings (cache paths, etc.) |

---

## Decisions

### D-01: Documentation Format

**Decision:** **C) Both** — Markdown files in `docs/` + CLI help for quick lookup

**Rationale:**
- Long-term reference documentation in `docs/config.md` for comprehensive understanding
- CLI access via `tdoc-crawler config docs --section <name>` for quick inline help
- Users can access detailed docs via `docs/config.md` or quick help via CLI

**Implementation:**
- `docs/config.md` — Complete config reference with tables, examples, descriptions
- CLI `tdoc-crawler config docs <section>` — Print section-specific help to console

---

### D-02: config validate Scope

**Decision:** **C) Full + warnings** — Syntax + values + warnings for missing optional

**Rationale:**
- Syntax-only validation is insufficient — users need to know if paths don't exist or values are out of range
- Warnings for missing optional values (like credentials) help users understand what they're missing without blocking

**Validation levels:**
1. **Syntax check** — TOML/YAML/JSON parses correctly
2. **Value validation** — Paths exist, numeric ranges valid, credentials have required format
3. **Warnings** — Missing optional values (credentials, optional filters) with helpful messages

**Exit codes:**
- `0` — All valid
- `1` — Syntax error
- `2` — Validation error (bad values)
- `3` — Warnings only (ok to proceed)

---

### D-03: 3gpp-ai Alignment Approach

**Decision:** **B) Reference pattern** — 3gpp-ai imports shared paths from TDocCrawlerConfig.path via CacheManager

**Rationale:**
- Keeps packages decoupled — 3gpp-ai remains independently installable
- Shared paths use CacheManager (already implemented and working)
- 3gpp-ai can use `3gpp-crawler.toml` as base config + `3gpp-ai.toml` for overrides
- Or users can use env vars exclusively (current behavior preserved)

**Current state:**
- `LightRAGConfig` in `packages/3gpp-ai/threegpp_ai/lightrag/config.py` — reads `TDC_AI_*` and `LIGHTRAG_*` env vars
- `AiConfig` in `packages/3gpp-ai/threegpp_ai/config.py` — legacy, also reads `TDC_AI_*` env vars
- Both already read `TDC_AI_*` env vars (main crawler uses `TDC_*`)

**What needs to change:**
- 3gpp-ai already uses `CacheManager` for paths (SSOT) — this is correct
- Document that `3gpp-crawler.toml` can be used as base, `3gpp-ai.toml` as override
- Ensure env var prefixes remain consistent (`TDC_AI_*` for AI settings)

**What should NOT change:**
- Don't merge `AiConfig` into `LightRAGConfig` — they serve different purposes
- Don't make 3gpp-ai depend on TDocCrawlerConfig directly — keep packages decoupled

---

### D-04: Migration Guide Location

**Decision:** **B) Section in `docs/config.md`** — Part of main config documentation

**Rationale:**
- All config documentation in one place — users won't have to search multiple files
- Natural flow: Overview → Config Options → Migration → Examples
- Can link from README and `.env.example` comments

**Structure of `docs/config.md`:**
```markdown
# Configuration Guide

## Overview
## Configuration Options
### Path Settings
### HTTP Settings
### Credential Settings
### Crawl Settings
## Migration from .env
## Examples
```

---

### D-05: Auto-Generation Approach

**Decision:** **A) Pydantic introspection** — Generate from `model_fields` and `Field(description=...)` at build time

**Rationale:**
- Documentation always stays in sync with code — no drift possible
- Single source of truth in the Pydantic models
- CI can regenerate docs on every build
- Manual overrides possible via docstring processing

**Implementation:**
- Create `scripts/generate_config_docs.py` that:
  1. Introspects `TDocCrawlerConfig` and nested models
  2. Extracts field names, descriptions, defaults, types
  3. Outputs Markdown table format
  4. Run via `uv run scripts/generate_config_docs.py > docs/config_reference.md`
- Document the generation in `docs/config.md` as: "This reference is auto-generated. Run `uv run scripts/generate_config_docs.py` to update."

**Note:** This was preferred over C) Hybrid because the user wants complete automation — generated tables AND manual narrative can be combined by having the generator output raw tables that humans can then add context around.

---

## the agent's Discretion

The following items are left to the implementer's discretion:

1. **CLI docs command interface** — Exact flag names for `tdoc-crawler config docs` (e.g., `--section`, `--format`, `--output`)

2. **Validation warning granularity** — Which specific conditions trigger warnings vs errors

3. **Generator script location** — `scripts/generate_config_docs.py` vs `src/tdoc_crawler/config/scripts/generate_docs.py`

4. **Docstring format in Pydantic models** — Whether to use Google-style or NumPy-style docstrings for the narrative sections

---

## Deferred Ideas

The following ideas were discussed but deferred to future phases:

1. **Config profiles (dev/staging/production)** — v2 requirement, out of scope for v1
2. **Interactive config validation** — `tdoc-crawler config doctor` with interactive fixes
3. **Config diff tool** — Compare config files across environments

---

## Files to Create/Modify

### New Files
- `scripts/generate_config_docs.py` — Config doc generator
- `docs/config.md` — Main config documentation with migration guide
- `.planning/phases/04-documentation/DISCUSSION-LOG.md` — This discussion log

### Files to Modify
- `src/tdoc_crawler/cli/config_cmd.py` — Add `validate` and `docs` commands
- `.env.example` — Update with all supported variables (DOCS-03)
- `src/tdoc_crawler/config/__init__.py` or `export.py` — Add validation logic
- `packages/3gpp-ai/` — Add reference to 3gpp-crawler.toml base config in docs

### No Changes Needed
- `packages/3gpp-ai/threegpp_ai/lightrag/config.py` — Already uses CacheManager correctly
- `packages/3gpp-ai/threegpp_ai/config.py` — Legacy but functional, can be documented

---

## Dependencies

- **Phase 1-3 complete** — TDocCrawlerConfig, CacheManager, load_cli_config() all implemented
- **No new dependencies** — Using existing pydantic introspection capabilities

---

## Blockers/Concerns

None identified during discussion.

---

*Context created: 2026-03-30*
