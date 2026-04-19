# Roadmap — 3GPP Crawler Codebase Improvement

## Phases

- [x] **Phase 01: Normalization & Progress Bars** - Consolidate duplicate normalization logic and fix progress bar document counts (completed 2026-04-12)
- [ ] **Phase 2: Checkout, Graph, Deprecation & Config** - Fix checkout paths, datetime errors, deprecated imports, and config drift

---

## Phase Details

### Phase 01: Normalization & Progress Bars

**Goal**: Eliminate duplicate normalization code and fix progress bar UX issues so users see document counts during long operations

**Depends on**: Nothing

**Requirements**: NORM-01, NORM-02, PROGRESS-01, PROGRESS-02

**Success Criteria** (what must be TRUE):
1. All normalization functions exist in single location (`src/tdoc_crawler/utils/normalization.py`)
2. `meetings/utils.py` re-exports from normalization.py, no duplicate functions
3. 6+ files importing normalization use single source (verified via grep)
4. Unit tests exist for all normalization functions covering edge cases
5. Progress bar shows "N/N" format (e.g., "5/69") during `workspace process`
6. Progress bar shows "N/N" format during `add_members` command

**Plans**: 2 plans

**Plan list:**
- [x] 01-normalization-PLAN.md — Consolidate normalization logic and add unit tests
- [x] 02-progress-PLAN.md — Fix progress bar display to show document counts

---

### Phase 2: Checkout, Graph, Deprecation & Config

**Goal**: Fix checkout path issues, datetime scope errors in graph building, remove deprecated imports, and align config defaults

**Depends on**: Phase 1

**Requirements**: CHECKOUT-01, GRAPH-01, DEPRECATED-01, CONFIG-01

**Success Criteria** (what must be TRUE):
1. Empty folder detection triggers re-download correctly
2. "No document files found" warning no longer appears for valid TDocs with empty folders
3. Graph building completes without datetime scope errors
4. Errors in graph building are caught and reported with meaningful messages
5. No import errors from deprecated modules (AiStorage, EmbeddingsManager, tdoc_ai.operations.pipeline, lancedb)
6. `.env.example` embedding model matches code defaults in `threegpp_ai/config.py`

**Plans**: 3 plans

**Plan list:**
- [ ] 02-01-PLAN.md — Fix checkout empty folder detection and re-download triggers
- [ ] 02-02-PLAN.md — Add graph error handling and verify deprecated imports removed
- [ ] 02-03-PLAN.md — Align embedding model defaults between .env.example and code

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 01. Normalization & Progress Bars | 2/2 | Complete    | 2026-04-12 |
| 2. Checkout, Graph, Deprecation & Config | 0/0 | Not started | - |

---

*Last updated: 2026-04-12*
