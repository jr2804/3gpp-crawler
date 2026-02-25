# Feature Specification: Replace DOCX Extraction Engine

**Feature Branch**: `001-replace-docling-extraction`
**Created**: 2026-02-25
**Status**: Draft
**Input**: User description: "Investigate and fix DOCX extraction design by replacing the legacy extractor with either markitdown or kreuzberg based on best fit for current implementation phase"

## Clarifications

### Session 2026-02-25

- Q: Should removal be enforced across specs and code artifacts without keeping legacy extractor dependencies or references? → A: Yes, enforce complete removal across specification and implementation scope.
- Q: For RAG/GraphRAG, should this phase switch fully to Kreüzberg-native embeddings/chunking or keep compatibility with markdown-first contracts? → A: Use a hybrid approach: Kreüzberg-rich extraction now, while preserving markdown artifact and current embedding/storage contracts for this phase.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Reliable Extraction for Large TDocs (Priority: P1)

As a developer running the AI pipeline, I need large DOCX TDocs to be converted to usable markdown reliably, so the pipeline can complete instead of stalling or failing on long documents.

**Why this priority**: Extraction is the first critical transformation step and currently blocks downstream embedding and summarization for large files.

**Independent Test**: Can be fully tested by processing a representative large DOCX input and verifying the markdown artifact is created and non-empty within the defined success threshold.

**Acceptance Scenarios**:

1. **Given** a checked-out TDoc folder containing a large DOCX file, **When** extraction runs, **Then** markdown output is produced and stored for downstream stages.
1. **Given** a large DOCX file previously failing with the legacy extractor, **When** the replacement extractor runs, **Then** extraction completes without pipeline stage failure.

______________________________________________________________________

### User Story 2 - Safe Migration With Existing Pipeline Behavior (Priority: P2)

As a maintainer, I need extraction engine replacement to preserve existing status tracking and artifact contracts, so currently implemented pipeline and CLI flows keep working.

**Why this priority**: Regressions in status transitions, `.ai` artifacts, or idempotency would break completed implementation phases and user trust.

**Independent Test**: Can be tested independently by running the existing extraction and pipeline tests and confirming unchanged user-visible behavior except for extractor reliability/performance improvements.

**Acceptance Scenarios**:

1. **Given** an already processed TDoc with unchanged source content, **When** extraction is re-invoked, **Then** idempotency behavior remains intact and unnecessary rework is avoided.
1. **Given** successful extraction, **When** embedding and summarization stages start, **Then** they consume the same markdown artifact location and continue normally.

______________________________________________________________________

### User Story 3 - Decision Transparency for Extractor Choice (Priority: P3)

As a project stakeholder, I need a clear comparison and chosen option for this phase, so implementation can proceed with low delivery risk.

**Why this priority**: Two alternatives are viable; explicit decision criteria prevent churn and rework.

**Independent Test**: Can be tested independently by reviewing a documented decision that maps current phase constraints to a selected extractor and acceptance expectations.

**Acceptance Scenarios**:

1. **Given** both candidate extractors are considered, **When** phase-fit evaluation is completed, **Then** one option is selected with explicit rationale.
1. **Given** the selected option is approved for this phase, **When** tasks are planned, **Then** they follow the selected migration path without ambiguity.

______________________________________________________________________

### Edge Cases

- Large DOCX includes mixed content (tables, figures, long headings) and extraction must still yield meaningful markdown text structure.
- Extractor dependency is unavailable at runtime and pipeline must fail with actionable error context instead of silent fallback corruption.
- Multiple DOCX files exist in one TDoc folder and classification-selected main file must be the one extracted.
- Extracted markdown is extremely large and must remain storable and readable by downstream stages without truncation-induced stage failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST replace the current legacy DOCX extraction path with exactly one selected alternative for this phase.
- **FR-002**: The selected extractor MUST provide structured extraction outputs (including tables/figures/metadata/language/keywords where available) and MUST also produce markdown artifacts consumable by existing embedding and summarization stages.
- **FR-003**: Extraction of representative large TDoc DOCX inputs (several hundred pages) MUST complete successfully and produce non-empty markdown output.
- **FR-004**: The system MUST preserve existing extraction artifact location and naming contract used by the pipeline (`.ai/<TDOC_ID>.md`).
- **FR-005**: The system MUST preserve idempotency behavior based on source change detection so unchanged inputs avoid unnecessary extraction work.
- **FR-006**: The system MUST surface extractor failures with actionable error messages that identify the affected TDoc and input file.
- **FR-007**: The phase outcome MUST include an explicit extractor decision with rationale comparing markitdown and kreuzberg against current implementation maturity.
- **FR-008**: Every feature MUST begin as a standalone library with a defined public
  interface before application integration.
- **FR-009**: Every library MUST expose a CLI that accepts text input and emits text
  output, and MUST provide a JSON output mode for structured data.
- **FR-010**: Unit tests MUST be written, user-approved, and verified failing before
  implementation begins.
- **FR-011**: Python implementations MUST use `pyproject.toml` with `uv`, include type
  hints and Google-style docstrings for public code, use `logging` instead of `print`,
  rely on `pathlib` for file paths, and keep Ruff and Ty checks clean without
  suppressions unless explicitly approved.
- **FR-012**: All new code MUST be placed in the correct domain package (`tdocs/`,
  `meetings/`, or `specs/`); domain logic MUST NOT appear in `cli/`, `parsers/`, or
  `utils/`; the legacy `crawlers/` package MUST NOT be referenced.
- **FR-013**: Before implementing any new functionality, existing code MUST be searched
  for equivalent implementations; CLI code MUST only delegate to core library functions
  and MUST NOT duplicate domain logic.
- **FR-014**: For core crawler source traffic (3GPP/WhatTheSpec/portal), all HTTP
  requests MUST use `create_cached_session()` from `tdoc_crawler.http_client`; direct
  HTTP calls to those sources are prohibited. AI model-provider traffic MAY be exempt,
  but the feature MUST explicitly document the exemption and approved client path.
- **FR-015**: The implementation MUST remove all legacy extractor references from code and configuration, including imports, fallback paths, and dependency declarations.
- **FR-016**: For this phase, embeddings and retrieval contracts MUST remain compatible with existing storage/query behavior; native Kreüzberg embedding/chunk schemas MAY be evaluated but MUST NOT replace current contracts in this phase.

### Selected Option for Current Phase

- **Decision**: Use a **hybrid approach**: integrate **Kreüzberg** for rich extraction signals while preserving markdown artifact compatibility and existing embedding/storage contracts.
- **Rationale**:
  - Kreüzberg directly supports structured extraction for tables, figures/images, metadata, language detection, and keywords, which benefits RAG/GraphRAG quality.
  - A full contract replacement in the same phase would introduce higher migration risk across embeddings, storage schema, query behavior, and completed tests.
  - Hybrid delivery captures near-term retrieval quality gains while keeping pipeline stability and delivery velocity.
- **Scope Boundaries for This Phase**:
  - Keep `.ai/<TDOC_ID>.md` as the canonical downstream compatibility artifact.
  - Add structured extraction outputs as complementary artifacts/metadata for retrieval enrichment.
  - Defer full native Kreüzberg chunk/embedding contract takeover to a later, explicit migration phase.

### Key Entities *(include if feature involves data)*

- **Extraction Candidate**: A source document selected for conversion, including TDoc ID, file path, and source hash for idempotency checks.
- **Markdown Artifact**: Extracted text output tied to one TDoc and stored as the canonical downstream input.
- **Structured Extraction Payload**: Optional rich extraction output (tables, figure references, metadata, language, keywords) linked to the same TDoc for retrieval and graph enrichment.
- **Processing Status**: Stage-tracking record for classification, extraction, embedding, summarization, graphing, completion, and failure metadata.

### Assumptions

- A representative large-file benchmark set exists in the project test assets or can be provided during implementation.
- Existing pipeline stage contracts and artifact conventions must remain stable during this phase.
- Rich extraction payload is integrated as additive metadata in this phase without breaking existing markdown-based contracts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of representative large DOCX inputs complete extraction without stage failure.
- **SC-002**: Median extraction time for representative large DOCX inputs is reduced by at least 70% compared with the current legacy-extractor baseline.
- **SC-003**: 100% of successful extraction runs produce a non-empty markdown artifact consumable by downstream stages.
- **SC-004**: Existing extraction, pipeline, and CLI behaviors that are unrelated to extractor internals remain backward-compatible in automated tests.
- **SC-005**: For successful extractions, structured extraction metadata is available for at least one representative large DOCX test case and can be consumed without breaking existing pipeline stages.
