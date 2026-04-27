# Requirements: 3GPP AI Document Intelligence

**Defined:** 2026-04-27
**Core Value:** Extract technically accurate, traceable document structure and meaning from complex PDFs into deterministic Markdown and canonical JSON artifacts.

## v1.1 Requirements

### Framework and Baseline

- [x] **FRMW-01**: The milestone documents and ratifies one primary llm-wiki framework with explicit rationale and tradeoff matrix.
- [x] **FRMW-02**: The selected framework integration profile is implemented without reintroducing vector-first default behavior.

### Wiki Compilation Contracts

- [ ] **WIKI-01**: The system compiles deterministic wiki pages from canonical extraction outputs for TDocs/specs/extra documents.
- [ ] **WIKI-02**: Every wiki page section includes stable provenance fields linking to source document/page/element IDs.
- [ ] **WIKI-03**: Re-running wiki compilation on unchanged inputs yields byte-stable page outputs and unchanged compile manifests.
- [ ] **WIKI-04**: Incremental rebuild mode recompiles only pages impacted by changed source artifacts.

### Wiki Query and Trust

- [ ] **QUERY-01**: Query mode retrieves from wiki pages/topics as primary substrate rather than raw chunk/vector retrieval.
- [ ] **QUERY-02**: Answer payloads include explicit citations to wiki sections and source coordinates.
- [ ] **QUERY-03**: Strict mode blocks uncited claims in final answer payloads.
- [ ] **QUERY-04**: Release/version-aware routing prevents mixing incompatible spec revisions without explicit conflict reporting.

### Migration and Decommission

- [ ] **MIGR-01**: Legacy LightRAG-first command paths are deprecated with clear migration guidance and compatibility warnings.
- [ ] **MIGR-02**: Documentation is updated to remove default RAG/embedding-first language and describe the wiki-first architecture.
- [ ] **MIGR-03**: Any retained fallback mode requires explicit opt-in and emits telemetry/metadata indicating non-wiki path usage.

### Quality and Operations

- [ ] **QUAL-01**: Existing extraction quality reports gate wiki publish; failed extraction artifacts cannot publish wiki pages.
- [ ] **QUAL-02**: Regression tests cover deterministic compile behavior, provenance mapping, and citation completeness.
- [ ] **QUAL-03**: CLI status output reports wiki build health (counts, failed pages, last compile hash).

## v2+ Requirements

### Advanced Retrieval Extensions

- **EXT-01**: Optional semantic retrieval add-on is introduced only after lexical wiki baseline shows measurable recall gaps.
- **EXT-02**: Multi-backend retrieval abstraction is added once scale/performance thresholds justify backend diversity.
- **EXT-03**: Advanced cross-release conflict synthesis is added with evaluator-backed acceptance criteria.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Reintroduce embeddings/vector retrieval as default in v1.1 | Directly conflicts with llm-wiki migration objective |
| Query-time graph extraction/generation in v1.1 | Adds latency and nondeterminism before wiki baseline is proven |
| Autonomous wiki page rewriting without provenance lock | Violates standards-traceability and auditability expectations |
| Broad cloud-service productization changes | Milestone scope is architecture migration within existing CLI package |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FRMW-01 | Phase 07 | Complete |
| FRMW-02 | Phase 07 | Complete |
| WIKI-01 | Phase 08 | Pending |
| WIKI-02 | Phase 08 | Pending |
| WIKI-03 | Phase 08 | Pending |
| WIKI-04 | Phase 08 | Pending |
| QUERY-01 | Phase 09 | Pending |
| QUERY-02 | Phase 09 | Pending |
| QUERY-03 | Phase 09 | Pending |
| QUERY-04 | Phase 09 | Pending |
| MIGR-01 | Phase 10 | Pending |
| MIGR-02 | Phase 10 | Pending |
| MIGR-03 | Phase 10 | Pending |
| QUAL-01 | Phase 08 | Pending |
| QUAL-02 | Phase 09 | Pending |
| QUAL-03 | Phase 10 | Pending |

**Coverage:**

- v1.1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 after milestone initialization (v1.1 llm-wiki)*
