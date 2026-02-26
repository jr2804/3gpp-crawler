# Feature Specification: AI Documentation Improvements

**Feature Branch**: `003-ai-documentation-improvements`
**Created**: 2026-02-26
**Status**: Clarified
**Created**: 2026-02-26
**Updated**: 2026-02-26 (CLI redesign added)
**Input**: User description: "Let's put everything into a specification as you have suggested. Include my answers as part of the implementation: only mention 'openrouter/openrouter/free' as an easy and free example, even though its capabilities might be limited and that paid options might work better. yes, include '--auto-build' for the creation of workspaces. please fix hardcoded model strings"

**CLI Redesign Input**: "Current AI CLI has too many unnecessary commands. `process` and `status` should be internal only. `query` should only query workspaces. `graph` should be removed/integrated into query. Single TDoc actions should be `summarize` (with --words, --format, keywords+metadata) and `convert` (markdown). Workspace queries must always use RAG+GraphRAG."

## Clarifications

### Session 2026-02-26 (CLI Redesign)

- Q: For deprecated commands (`ai process`, `ai status`, `ai graph`), should we remove them entirely or show deprecation warnings? → A: Remove commands entirely
- Q: Should `ai summarize` work only on locally checked-out TDocs, or fetch remotely if needed? → A: Fetch remotely if needed (via WhatTheSpec/Portal)
- Q: When `ai query` uses both RAG+GraphRAG, how should results be presented? → A: Merged results (RAG embeddings + Graph relationships in same response)
- Q: Which output formats should `ai summarize` support? → A: All three formats (markdown default, JSON, YAML)
- Q: How strictly should `ai summarize --words 200` enforce the word count? → A: Soft target ±20% variance (e.g., 160-240 words acceptable)

______________________________________________________________________

## User Scenarios & Testing

### User Story 1 - Quick Start with Free AI Features (Priority: P1)

As a new user, I want to try the AI features without paying for API subscriptions, so I can evaluate whether the AI capabilities are useful for my workflow before committing to paid services.

**Why this priority**: This is the primary onboarding experience. Users need a zero-cost entry point to evaluate AI features. Without a clear free tier path, users may abandon the feature before trying it.

**Independent Test**: User can follow installation instructions, configure with free OpenRouter account, and successfully process a TDoc with AI features without any paid subscriptions.

**Acceptance Scenarios**:

1. **Given** a fresh installation of tdoc-crawler[ai], **When** user follows the installation guide, **Then** documentation clearly states to use `openrouter/openrouter/free` as the default LLM model
1. **Given** user has obtained a free OpenRouter API key, **When** user configures `.env` file with the key, **Then** the system processes documents successfully without requiring paid subscriptions
1. **Given** documentation mentions free tier limitations, **When** user reads the guide, **Then** they understand that paid options exist for better performance but are not required for basic functionality

______________________________________________________________________

### User Story 2 - Streamlined Workspace Creation (Priority: P2)

As a user working with multiple TDoc collections, I want to create a workspace and automatically build its knowledge base in one step, so I don't have to manually run separate commands for workspace creation and document processing.

**Why this priority**: Reduces friction in the common workflow. While users can manually run multiple commands, the auto-build option significantly improves the user experience for the typical use case.

**Independent Test**: User can create a workspace with `--auto-build` flag and the system automatically processes added documents without requiring a separate `ai process-all` command.

**Acceptance Scenarios**:

1. **Given** user wants to create a new workspace, **When** user runs `tdoc-crawler ai workspace create my-project --auto-build`, **Then** workspace is created and knowledge base building is automatically initiated
1. **Given** workspace created with auto-build, **When** documents are added via checkout, **Then** they are automatically processed without manual intervention
1. **Given** user prefers manual control, **When** user creates workspace without `--auto-build` flag, **Then** workspace is created but requires manual processing

______________________________________________________________________

### User Story 4 - CLI Command Redesign (Priority: P1)

As a user, I want a clean, purpose-driven CLI that separates single-TDoc operations from workspace-based analysis, so I can quickly understand which command to use for my task.

**Why this priority**: The current CLI has commands that don't align with user mental models. Single-TDoc operations should be simple transformations (summarize, convert), while workspace operations should be for analysis (query with RAG+GraphRAG). Internal operations (process, status) should not clutter the CLI.

**Independent Test**: User can successfully use `ai summarize` for single TDocs, `ai convert` for markdown conversion, and `ai query` for workspace analysis without confusion about command purposes.

**Acceptance Scenarios**:

1. **Given** user has a single TDoc, **When** user runs `ai summarize TDOC-ID --words 200 --format markdown`, **Then** system outputs a summary with specified word count, includes extracted keywords and metadata
1. **Given** user has a single TDoc, **When** user runs `ai convert TDOC-ID --output file.md`, **Then** system converts the TDoc to markdown format
1. **Given** user has a workspace with multiple TDocs, **When** user runs `ai query "find security enhancements" --workspace my-project`, **Then** system returns results using both RAG (semantic search) and GraphRAG (relationship-based) automatically
1. **Given** user runs old `ai process` command, **When** command is invoked, **Then** system shows deprecation message directing to workspace-based workflow
1. **Given** user runs old `ai status` command, **When** command is invoked, **Then** system shows deprecation message or the command is removed entirely

______________________________________________________________________

### User Story 3 - Correct Model Configuration (Priority: P3)

As a user configuring custom LLM models, I want the system to use my configured model instead of hardcoded defaults, so I can choose the best model for my needs and budget.

**Why this priority**: While the system works with defaults, power users need the flexibility to choose different models. Hardcoded values prevent this customization and may cause unexpected costs or behavior.

**Independent Test**: User can set `TDC_AI_LLM_MODEL` environment variable to any supported model and the summarization feature uses that model instead of a hardcoded value.

**Acceptance Scenarios**:

1. **Given** user sets `TDC_AI_LLM_MODEL=anthropic/claude-3-haiku`, **When** user runs `ai process`, **Then** summarization uses the configured model, not a hardcoded default
1. **Given** user has not configured a custom model, **When** user runs `ai process`, **Then** system uses the default model `openrouter/openrouter/free`
1. **Given** user wants to verify which model is being used, **When** user checks configuration, **Then** documentation clearly explains the model identifier format and supported providers

______________________________________________________________________

### Edge Cases

- **API/Service Unavailable**: When any LLM or embedding provider API is temporarily unavailable, system MUST provide a clear error message indicating the service is unreachable and exit gracefully. No automatic retry or re-routing to alternative providers.
- **Invalid Model Identifiers**: System MUST validate that the provider (first segment of model identifier) is in the supported allowlist at configuration time. If provider is invalid, provide clear error message with list of supported providers. If provider is valid but model name is incorrect, the error will be raised by the provider at first use with a clear error message.
- **Auto-build with Empty Workspace**: The `--auto-build` flag is a workspace property that applies only to newly added items. When workspace is created with `--auto-build` but no documents are added, the workspace is created successfully with auto-build enabled. When the last document is removed from a workspace, any RAG/GraphRAG entries for that workspace MAY be cleared regardless of auto-build setting.
- **Rate Limiting**: When any API provider returns a rate limit error, system MUST provide a clear error message indicating the rate limit was exceeded and exit gracefully. No exponential backoff or automatic retry is implemented.
- **Missing API Key**: When initializing a provider that typically requires authentication, system SHOULD log a warning if no API key is detected in the expected environment variable. System proceeds with the request anyway (as some providers may allow temporary free access). If the provider rejects the request due to missing/invalid API key, system provides a clear error message indicating which API key is required.

______________________________________________________________________

## Requirements

### Functional Requirements

- **FR-001**: System MUST use the configured `TDC_AI_LLM_MODEL` value from environment or config for all LLM operations, with no hardcoded model identifiers in the codebase
- **FR-002**: System MUST default to `openrouter/openrouter/free` as the LLM model when no custom model is configured
- **FR-003**: System MUST default to `ollama/embeddinggemma` as the embedding model when no custom model is configured
- **FR-004**: Documentation MUST prominently feature `openrouter/openrouter/free` as the recommended free-tier LLM option
- **FR-005**: Documentation MUST include a note that free tier options have limited capabilities compared to paid alternatives
- **FR-006**: System MUST support `--auto-build` flag for `ai workspace create` command that automatically initiates knowledge base construction
- **FR-020**: System MUST provide `ai summarize` command for single TDoc summarization with `--words` (default: 200), `--format` (markdown/json/yaml, default: markdown), and include extracted keywords and metadata in output
- **FR-021**: System MUST provide `ai convert` command for single TDoc markdown conversion with `--output` file path option
- **FR-022**: System MUST remove or deprecate `ai process` command (internal use only via workspace workflow)
- **FR-023**: System MUST remove or deprecate `ai status` command (internal use only)
- **FR-024**: System MUST restrict `ai query` command to workspace-only queries (no single-TDoc queries)
- **FR-025**: System MUST integrate GraphRAG into `ai query` command automatically (no separate `ai graph` command)
- **FR-026**: Workspace queries MUST always use both RAG (semantic embeddings) and GraphRAG (knowledge graph) together, not as separate options
- **FR-027**: Documentation MUST reflect the redesigned CLI structure with clear separation: single-TDoc commands (summarize, convert) vs workspace commands (create, add-members, query)

### Key Entities

- **Workspace**: Logical container for organizing TDocs and specifications for focused AI analysis, stored in LanceDB
- **ProcessingStatus**: Tracks the AI processing state of a document through pipeline stages (CLASSIFY, EXTRACT, EMBED, SUMMARIZE, GRAPH)
- **Knowledge Graph**: Graph-based representation of relationships between TDocs, built from extracted content and semantic analysis
- **Model Configuration**: Environment-based configuration for LLM and embedding models, including provider, model name, and API credentials

______________________________________________________________________

## Success Criteria

### Measurable Outcomes

- **SC-001**: New users can complete AI feature setup and process their first TDoc in under 10 minutes following documentation
- **SC-012**: CLI command structure is intuitive: users can correctly identify which command to use for single-TDoc vs workspace operations without referring to documentation
- **SC-013**: `ai summarize` command produces output in all three formats (markdown, json, yaml) with correct word count constraints
- **SC-014**: `ai query` command automatically uses both RAG and GraphRAG for workspace queries (verified by code inspection)
- **SC-015**: Deprecated commands (`ai process`, `ai status`, `ai graph`) either removed or show clear deprecation messages directing users to new workflow
