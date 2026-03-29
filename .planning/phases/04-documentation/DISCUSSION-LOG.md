# Phase 4: Documentation & Tooling — Discussion Log

**Date:** 2026-03-30  
**Phase:** 4 of 4 (Documentation & Tooling)

---

## Gray Areas Presented

### 📋 Decision 1: Documentation Format

**Question:** How should config documentation be delivered?

**Options presented:**
- A) Markdown files only (`docs/config.md`)
- B) CLI help generation (`tdoc-crawler config docs --section`)
- C) Both — Markdown for reference + CLI for quick lookup

**Decision: C) Both**

---

### 📋 Decision 2: `config validate` Scope

**Question:** How thorough should `config validate` be?

**Options presented:**
- A) Syntax-only — Check if TOML/YAML/JSON parses correctly
- B) Full validation — Syntax + validate values (paths exist, ranges valid)
- C) Full + warnings — Same as B but warn on missing optional values

**Decision: C) Full + warnings**

---

### 📋 Decision 3: 3gpp-ai Alignment Approach

**Question:** How should 3gpp-ai package align with main crawler config?

**Options presented:**
- A) Extension pattern — Add `ai:` section to TDocCrawlerConfig, 3gpp-ai extends it
- B) Reference pattern — 3gpp-ai keeps separate config but imports shared paths via CacheManager
- C) Merge — Deprecate AiConfig, move all to LightRAGConfig

**Decision: B) Reference pattern**

---

### 📋 Decision 4: Migration Guide Location

**Question:** Where should the migration guide for .env users be located?

**Options presented:**
- A) `docs/migration.md` — Standalone migration guide
- B) `docs/config.md` section — Part of main config documentation
- C) `MIGRATION.md` at root — Highly visible, can link from README

**Decision: B) Section in docs/config.md**

---

### 📋 Decision 5: Auto-Generation Approach

**Question:** How should config documentation be generated from pydantic models?

**Options presented:**
- A) Pydantic introspection — Generate from `model_fields` and `Field(description=...)` at build time
- B) Manual docs with CI checks — Write docs manually, CI checks sync
- C) Hybrid — Generated tables + manual narrative sections

**Decision: A) Pydantic introspection**

---

## Summary of Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D-01: Documentation Format | C) Both | Long-term reference in docs/ + CLI for quick lookup |
| D-02: config validate Scope | C) Full + warnings | Most helpful, catches issues early with helpful messages |
| D-03: 3gpp-ai Alignment | B) Reference pattern | Keeps packages decoupled, CacheManager is already SSOT for paths |
| D-04: Migration Guide Location | B) docs/config.md section | All config docs in one place, natural user flow |
| D-05: Auto-Generation | A) Pydantic introspection | Complete automation, no drift possible |

---

## Key Implementation Notes

1. **3gpp-ai Alignment (D-03):** The `LightRAGConfig` and `AiConfig` in 3gpp-ai already read `TDC_AI_*` env vars. The main crawler uses `TDC_*` prefix. No conflict. CacheManager is already used for paths — this is the SSOT. Document that users can use `3gpp-crawler.toml` as base + `3gpp-ai.toml` as override.

2. **Auto-generation (D-05):** Create `scripts/generate_config_docs.py` that introspects `TDocCrawlerConfig` using pydantic's `model_fields` and `Field(description=...)`. Output Markdown tables. Run manually or in CI.

3. **config validate (D-02):** Exit codes: 0=valid, 1=syntax error, 2=validation error, 3=warnings only.

---

*Discussion concluded: 2026-03-30*
