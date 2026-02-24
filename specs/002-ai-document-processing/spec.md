# Feature Specification: AI Document Processing Pipeline

**Feature Branch**: `002-ai-document-processing`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "AI-based processing of downloaded files: document classification, DOCX-to-Markdown extraction, embeddings generation, LLM summarization, and temporal graph-RAG construction for 3GPP TDocs"
**Epic**: tdc-b9w

## User Scenarios & Testing *(mandatory)*

### User Story 1 - DOCX-to-Markdown Extraction (Priority: P1)

A standards engineer has downloaded a batch of 3GPP TDocs via `tdoc-crawler`. They want
each DOCX document automatically converted to a clean Markdown file that preserves text,
headings, tables, and figure references so they can read, search, and version-control
the content without opening Word.

**Why this priority**: Markdown extraction is the foundational step on which every
downstream AI capability (embeddings, summaries, graph) depends. Without it, nothing
else can run. It also delivers standalone value: searchable plain-text copies of TDocs.

**Independent Test**: Run `tdoc-crawler ai process --tdoc-id SP-123456` on a
previously-downloaded TDoc that contains at least one table and one heading hierarchy.
Verify a `.ai/` subfolder is created with a Markdown file whose tables and headings
match the source DOCX.

**Acceptance Scenarios**:

1. **Given** a downloaded TDoc folder containing one DOCX file, **When** the user runs
   `ai process --tdoc-id <id>`, **Then** a `.ai/<tdoc_id>.md` Markdown file is created
   preserving headings, paragraphs, and tables.
1. **Given** a downloaded TDoc folder containing one DOCX file with embedded figures,
   **When** extraction runs, **Then** figures are referenced in the Markdown with alt
   text or caption text, and images are saved alongside.
1. **Given** a TDoc that was already extracted, **When** extraction runs again, **Then**
   it is skipped (idempotent) unless the source file has changed.
1. **Given** a DOCX with 3GPP-specific formatting (section numbering like "5.3.2.1",
   change bars, tracked changes), **When** extraction runs, **Then** section numbering
   and accepted changes are preserved in Markdown.

______________________________________________________________________

### User Story 2 - Main Document Identification (Priority: P2)

When a TDoc download folder contains multiple DOCX files (e.g., a cover note plus the
actual contribution), the user wants the system to automatically determine which file
is the "main" document and which are secondary, so downstream processing focuses on the
primary content.

**Why this priority**: A prerequisite for reliable extraction and summarization at
scale. Many TDoc folders contain 2-5 files; processing the wrong one wastes compute and
produces misleading summaries.

**Independent Test**: Prepare three test TDoc folders: one with a single DOCX, one with
two (cover note + contribution), one with three files including a revision. Run document
identification on all three and verify the main document is correctly identified in each
case.

**Acceptance Scenarios**:

1. **Given** a TDoc folder with a single DOCX file, **When** classification runs,
   **Then** it is marked as `is_main_document=True` with confidence 1.0.
1. **Given** a TDoc folder with two DOCX files (one small cover note, one larger
   contribution), **When** classification runs, **Then** the larger, more structured
   file is marked as main.
1. **Given** a TDoc folder with files named `*_final.docx` and `*_draft.docx`, **When**
   classification runs, **Then** the `final` variant is marked as main.
1. **Given** a TDoc with the `is_revision_of` field populated, **When** classification
   runs, **Then** the latest revision is preferred as whole.

______________________________________________________________________

### User Story 3 - AI Processing Pipeline Orchestration (Priority: P3)

The user wants to run the full AI pipeline across all downloaded TDocs in a single
command (`ai process --all`), with the system executing stages in order (classify,
extract, embed, summarize, graph), supporting resume from failure, and processing only
new or updated documents incrementally.

**Why this priority**: Orchestration ties the individual stages together for batch
operations. It is lower priority than the individual stages (P1 and P2) because each
stage must work standalone first.

**Independent Test**: Download 5 TDocs, run `ai process --all`. Interrupt after 3 are
extracted. Re-run `ai process --all` and verify only the remaining 2 are processed.
Check `ai status` to confirm all 5 show as completed.

**Acceptance Scenarios**:

1. **Given** 10 downloaded TDocs with none processed, **When** `ai process --all` runs,
   **Then** all 10 go through classification, extraction, and any enabled downstream
   stages, with progress reported.
1. **Given** a pipeline run interrupted at the extraction stage for TDoc #7, **When**
   `ai process --all` runs again, **Then** processing resumes from TDoc #7's extraction
   stage without re-processing TDocs #1-6.
1. **Given** 10 previously processed TDocs and 3 newly downloaded ones, **When**
   `ai process --new-only` runs, **Then** only the 3 new TDocs are processed.
1. **Given** an extraction failure for a specific TDoc, **When** the pipeline completes,
   **Then** the failure is logged and the TDoc is marked as `failed` with an error
   message; other TDocs continue processing.

______________________________________________________________________

### User Story 4 - Embeddings Generation (Priority: P4)

After extraction, the user wants each document's Markdown content chunked into
meaningful segments (sections, paragraphs) and embedded as vectors so that semantic
search queries can retrieve relevant content across the entire TDoc corpus.

**Why this priority**: Embeddings enable semantic search, which is a core prerequisite
for the RAG query pipeline and for the LLM summarizer's context assembly.

**Independent Test**: Process 3 TDocs through extraction. Run the embeddings stage.
Query "uplink power control" and verify that at least one chunk from a relevant TDoc
appears in the top-5 results.

**Acceptance Scenarios**:

1. **Given** a Markdown file for a TDoc, **When** embeddings generation runs, **Then**
   the document is split into chunks and each chunk's vector is stored with metadata
   (TDoc ID, section, chunk position).
1. **Given** a previously-embedded TDoc whose source has not changed, **When** embeddings
   generation runs again, **Then** it is skipped.
1. **Given** 50 TDoc Markdown files, **When** embeddings generation runs in batch,
   **Then** processing completes within a reasonable time using configurable parallelism.
1. **Given** a change in the configured embedding model, **When** the user triggers
   re-embedding, **Then** all existing embeddings are regenerated with the new model and
   the model version is recorded.

______________________________________________________________________

### User Story 5 - LLM Summarization (Priority: P5)

The user wants each processed TDoc to have an automatically generated abstract
(150-250 words) and a structured technical summary with key points, action items, and
decisions, so they can quickly triage TDocs without reading the full document.

**Why this priority**: Summaries provide immediate user value but depend on extraction
(P1) being complete. They do not block embeddings or graph construction.

**Independent Test**: Process a known TDoc through extraction. Run summarization.
Verify the generated abstract is between 150-250 words and mentions the TDoc's key
topic.

**Acceptance Scenarios**:

1. **Given** an extracted Markdown TDoc, **When** summarization runs, **Then** an
   abstract of 150-250 words and a structured summary with key points are stored.
1. **Given** a TDoc that is a Change Request, **When** summarization runs, **Then** the
   summary includes the affected specification, the proposed change, and the rationale.
1. **Given** a previously-summarized TDoc, **When** summarization runs again without
   source changes, **Then** it is skipped.
1. **Given** no LLM endpoint configured, **When** summarization is attempted, **Then**
   a clear error message is shown indicating the missing configuration.

______________________________________________________________________

### User Story 6 - Temporal Graph Construction (Priority: P6)

The user wants a knowledge graph that connects TDocs, meetings, specifications, work
items, and extracted concepts with temporal validity, so they can query the evolution of
a feature or topic across meetings (e.g., "How did the echo canceller test setup evolve
from SA4#120 to SA4#125?").

**Why this priority**: The graph-RAG capability is the most complex stage and depends on
all prior stages. It delivers the highest long-term value but has the most dependencies.

**Independent Test**: Process 10 TDocs from 3 different meetings that discuss the same
work item. Build the graph. Query "evolution of [work item] across meetings" and verify
the response includes a chronologically ordered chain of TDoc references.

**Acceptance Scenarios**:

1. **Given** extracted TDocs from multiple meetings, **When** graph construction runs,
   **Then** nodes are created for TDocs, meetings, specs, and concepts, and edges
   represent relationships (discusses, revises, references, supersedes).
1. **Given** temporal graph data, **When** the user queries `ai graph --query "history of feature X"`, **Then** results are returned in chronological order with meeting
   references.
1. **Given** new TDocs added after initial graph construction, **When** graph update
   runs, **Then** new nodes and edges are added incrementally without rebuilding the
   entire graph.
1. **Given** two TDocs where one explicitly references the other's TDoc ID, **When**
   graph construction runs, **Then** a `references` edge connects them.

______________________________________________________________________

### User Story 7 - CLI Commands and Status Reporting (Priority: P3)

The user wants CLI commands to trigger processing, check status, and query AI-generated
data, following the same patterns as existing `tdoc-crawler` commands.

**Why this priority**: Equal to pipeline orchestration (P3) since the CLI is the
user-facing entry point for all AI operations.

**Independent Test**: Run `tdoc-crawler ai --help` and verify all subcommands are listed.
Run `ai status --tdoc-id <id>` on a processed TDoc and verify it shows the current
stage and completion status.

**Acceptance Scenarios**:

1. **Given** the CLI is installed, **When** the user runs `tdoc-crawler ai --help`,
   **Then** subcommands `process`, `status`, `query`, and `graph` are listed with
   descriptions.
1. **Given** a TDoc at various processing stages, **When** `ai status --tdoc-id <id>`
   runs, **Then** the output shows which stages are complete, in-progress, or pending.
1. **Given** processed TDocs with summaries, **When** `ai query --tdoc-id <id> "What is this TDoc about?"`, **Then** an answer grounded in the TDoc's content is
   returned.
1. **Given** the `--json` flag is passed, **When** any AI command runs, **Then** output
   is valid JSON.

______________________________________________________________________

### Edge Cases

- What happens when a TDoc download folder contains no DOCX files (only PDF or ZIP)?
  The system should log a warning and skip extraction, marking the TDoc as `failed`.
- What happens when the configured LLM endpoint is unreachable? The summarization and
  graph stages should fail gracefully with a clear error; earlier stages (extraction,
  embeddings) should still succeed.
- What happens when a DOCX file is corrupt or password-protected? The extraction stage
  should log the error, mark the TDoc as `extraction_failed`, and continue with the next
  TDoc.
- What happens when the embedding model produces vectors of a different dimension than
  previously stored embeddings? The system should detect the mismatch and require
  explicit re-embedding of the entire corpus.
- What happens when the same TDoc is downloaded to multiple meeting folders (duplicate)?
  The system should use TDoc ID normalization (`.upper()`) and process each unique TDoc
  ID only once.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST convert DOCX files to Markdown preserving headings, paragraphs,
  tables (with structure), and figure references.
- **FR-002**: System MUST classify files in multi-file TDoc folders as "main" or
  "secondary" with a confidence score and audit trail of heuristics applied.
- **FR-003**: System MUST split extracted Markdown into chunks and generate vector
  embeddings with per-chunk metadata (TDoc ID, section, position, model version).
- **FR-004**: System MUST generate abstracts (150-250 words) and structured summaries
  for each processed TDoc using a configurable LLM endpoint.
- **FR-005**: System MUST construct a temporal knowledge graph connecting TDocs,
  meetings, specifications, work items, and extracted concepts with temporal validity
  fields.
- **FR-006**: Every feature MUST begin as a standalone library with a defined public
  interface before application integration.
- **FR-007**: Every library MUST expose a CLI that accepts text input and emits text
  output, and MUST provide a JSON output mode for structured data.
- **FR-008**: Unit tests MUST be written, user-approved, and verified failing before
  implementation begins.
- **FR-009**: Python implementations MUST use `pyproject.toml` with `uv`, include type
  hints and Google-style docstrings for public code, use `logging` instead of `print`,
  rely on `pathlib` for file paths, and keep Ruff and Ty checks clean without
  suppressions unless explicitly approved.
- **FR-010**: All new code MUST be placed in the new `ai/` domain package under
  `src/tdoc_crawler/ai/`; domain logic MUST NOT appear in `cli/`, `parsers/`, or
  `utils/`; the legacy `crawlers/` package MUST NOT be referenced.
- **FR-011**: Before implementing any new functionality, existing code MUST be searched
  for equivalent implementations; CLI code MUST only delegate to core library functions
  and MUST NOT duplicate domain logic.
- **FR-012**: All HTTP requests that are deterministic and cacheable MUST use
  `create_cached_session()` from `tdoc_crawler.http_client`; direct HTTP calls to
  external services are prohibited. LLM calls via litellm are exempt from caching, and
  local embedding generation does not use HTTP.
- **FR-013**: All AI processing stages MUST be idempotent: re-running a stage on an
  already-processed TDoc with unchanged inputs MUST produce no side effects.
- **FR-014**: The pipeline MUST support incremental processing: only new or updated
  TDocs are processed by default.
- **FR-015**: The pipeline MUST support resume from failure: after a crash, re-running
  picks up from the last successfully completed stage per TDoc.
- **FR-016**: AI configuration (model endpoints, chunk sizes, embedding model, prompt
  templates) MUST be managed via a configuration model, not hard-coded.
- **FR-017**: Graph construction MUST support incremental updates: new nodes and edges
  are merged into the existing graph without requiring a full rebuild.
- **FR-018**: AI processing data (embeddings, summaries, graph, processing status) MUST
  be stored in its own file-system-based storage, separate from the tdoc-crawler SQLite
  database. No additional server infrastructure is required. The tdoc-crawler core
  package remains a standalone program; the AI addon reads TDoc metadata from
  tdoc-crawler's database but writes all AI artifacts to its own store.

### Key Entities

- **ProcessingStatus**: Tracks the current AI processing state for each TDoc (stages:
  pending, classifying, extracting, embedding, summarizing, graphing, completed, failed).
  Links to TDoc ID, timestamps per stage, and error messages.
- **DocumentClassification**: Records main/secondary classification for each file in a
  TDoc folder. Includes confidence score, decisive heuristic, and file path.
- **DocumentChunk**: A segment of extracted Markdown text with position metadata (TDoc ID,
  section heading, chunk index, character offsets) and its embedding vector metadata.
- **DocumentSummary**: The LLM-generated abstract and structured summary for a TDoc.
  Includes model ID, prompt version, and generation timestamp.
- **GraphNode**: An entity in the knowledge graph (TDoc, Meeting, Spec, WorkItem, CR,
  Company, or Concept). Has temporal validity fields (valid_from, valid_to) and a type
  discriminator.
- **GraphEdge**: A typed relationship between two GraphNodes (discusses, revises,
  references, supersedes, authored_by, merged_into, presented_at). Has weight, temporal
  context, and source provenance.

## Assumptions

- TDoc files have already been downloaded and extracted by the existing `tdoc-crawler`
  checkout/fetch workflow before AI processing begins.
- The `.ai/` subfolder convention within each TDoc's extraction folder is acceptable for
  storing AI-generated artifacts (Markdown, metadata).
- A local or remote LLM endpoint (e.g., Ollama) will be available for summarization and
  graph entity extraction; the system does not ship or manage LLM model files.
- AI processing uses its own file-system-based storage (separate from tdoc-crawler's
  SQLite database). The AI addon reads TDoc metadata from the existing database but
  writes all AI-generated data (embeddings, summaries, graph, processing status) to a
  dedicated store. This keeps tdoc-crawler functional as a standalone tool.
- Embedding vectors will use a local model (e.g., BAAI/bge or similar) accessible via
  a Python library; no remote embedding API is required for the initial release.

## Constraints

- All AI processing runs locally on the user's machine; no data is sent to external
  cloud services unless the user explicitly configures a remote LLM endpoint.
- Batch processing must handle at least 500 TDocs without excessive memory usage
  (target: under 2 GB peak for non-LLM stages).
- The AI domain package (`src/tdoc_crawler/ai/`) MUST NOT introduce circular
  dependencies with existing domain packages (`tdocs/`, `meetings/`, `specs/`).
- AI dependencies (ML libraries, embedding models) should be optional extras
  (`tdoc_crawler[ai]`) to avoid bloating the base package for users who do not need AI
  features.

## Out of Scope

- Real-time or streaming LLM chat interface (this spec covers batch processing only).
- Training or fine-tuning of LLM or embedding models.
- PDF, PPT, or XLS extraction (DOCX is the initial target; other formats may be added
  in a future iteration following the same pipeline architecture).
- Graph visualization UI (the graph is queryable via CLI; visualization tools are a
  future feature).
- Multi-user access control or authentication for AI-generated data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can process a single TDoc through extraction and receive a readable
  Markdown file within 30 seconds.
- **SC-002**: The main document in a multi-file TDoc folder is correctly identified in
  at least 90% of cases (measured across a test set of 50 TDocs).
- **SC-003**: Semantic search over embedded chunks returns at least one relevant result
  in the top 5 for 80% of a curated set of 20 test queries.
- **SC-004**: LLM-generated abstracts are between 150-250 words for 95% of processed
  TDocs.
- **SC-005**: Re-running the full pipeline on an already-processed corpus completes
  within 10% of the original processing time (demonstrating effective idempotency and
  skip logic).
- **SC-006**: After a simulated crash at any stage, resume processing completes
  successfully without data loss or corruption.
- **SC-007**: Temporal graph queries return chronologically ordered results that match
  the known meeting sequence for at least 90% of test cases.
