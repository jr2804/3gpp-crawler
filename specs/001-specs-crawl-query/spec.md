# Feature Specification: Crawl and Query Specs

**Feature Branch**: `001-specs-crawl-query`
**Created**: 2026-02-05
**Status**: Draft
**Input**: User description: "Introduce crawl/query for 3GPP specs with crawl-specs and query-specs commands. Support metadata via 3gpp.org redirects to specification details (specificationId) and via whatthespec.net JSON API. Add database tables and models for specs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Crawl spec metadata from both sources (Priority: P1)

As a data curator, I want to crawl 3GPP specification metadata using both 3GPP.org and whatthespec.net so the system can build a complete, normalized catalog of specs.

**Why this priority**: This creates the foundational dataset that all queries and downstream workflows depend on.

**Independent Test**: Run a crawl for a known spec number and verify that stored metadata includes the spec title, type, versions, working group, and source attribution.

**Acceptance Scenarios**:

1. **Given** a valid spec number, **When** I run a crawl using the 3GPP.org source, **Then** the catalog stores metadata returned from the redirected specification details page.
2. **Given** a valid spec number, **When** I run a crawl using the whatthespec.net source, **Then** the catalog stores metadata returned by the JSON API.
3. **Given** a spec available from both sources, **When** I crawl using both sources, **Then** the catalog stores both source records and ties them to the same canonical spec number.

---

### User Story 2 - Checkout or open spec documents (Priority: P2)

As a maintainer, I want to checkout one or more specs or open a single spec document so the files are immediately available for review and downstream processing.

**Why this priority**: The metadata is only useful if the spec document can be retrieved reliably and placed in a predictable location.

**Independent Test**: Checkout a known spec revision using doc-only mode and confirm the document exists in the expected checkout folder path.

**Acceptance Scenarios**:

1. **Given** a resolved spec download URL, **When** I checkout the latest version, **Then** the zip contents are extracted to `checkout_dir/Specs/archive/<series>/<spec number>/<file name>/`.
2. **Given** doc-only mode is enabled, **When** the system locates a matching `.doc` or `.docx` entry in the remote zip, **Then** it downloads only that document and stores it in the expected checkout folder.
3. **Given** doc-only mode is enabled, **When** document identification fails, **Then** the system warns and downloads/extracts the full zip.
4. **Given** a spec zip that contains a single document plus attachments, **When** extraction completes, **Then** the document and attachments are stored together under the same checkout folder.
5. **Given** I run open-spec for a single spec, **When** the checkout completes, **Then** the document opens with the system default application.
6. **Given** I request a specific release value, **When** the release matches metadata, **Then** the corresponding version is downloaded and extracted.
7. **Given** I request a release that cannot be determined, **When** the command runs, **Then** it warns, skips that spec, and continues with remaining items if any.

---

### User Story 3 - Query spec catalog by key attributes (Priority: P3)

As an analyst, I want to query the spec catalog by number, title keyword, working group, and status so I can quickly find the specification metadata I need.

**Why this priority**: Querying is the primary way users access the catalog once it exists.

**Independent Test**: Run a query for a known spec number and confirm the returned record matches the stored metadata.

**Acceptance Scenarios**:

1. **Given** the catalog contains a spec with number 26.260, **When** I query by spec number, **Then** I receive the exact matching spec with its versions and source attribution.
2. **Given** the catalog contains multiple specs for a working group, **When** I query by working group, **Then** I receive all specs for that group.
3. **Given** the catalog contains specs with distinct statuses, **When** I query by status, **Then** I receive only the specs in the requested status.

---

### User Story 4 - Inspect source discrepancies (Priority: P4)

As a maintainer, I want to see when metadata differs between 3GPP.org and whatthespec.net so I can resolve discrepancies and trust the catalog.

**Why this priority**: Source discrepancies reduce confidence and require visibility to ensure accurate records.

**Independent Test**: Query a spec that exists in both sources and verify that differences in version lists or titles are visible.

**Acceptance Scenarios**:

1. **Given** both sources report different version lists for a spec, **When** I query the spec, **Then** I can see the version lists per source.
2. **Given** both sources report different titles, **When** I query the spec, **Then** I can see the title per source.

---

### Edge Cases

- What happens when a spec number does not exist in either source?
- How does the system handle a 3GPP.org redirect that does not include a specification id?
- What happens when whatthespec.net returns an empty or malformed response?
- How does the system handle conflicting metadata between sources for the same spec?
- What happens when a crawl is interrupted or partially completes?
- What happens when a spec download zip is missing expected document files?
- What happens when the checkout path already exists for the requested version?
- What happens when doc-only mode cannot locate a document entry in the remote zip?
- What happens when the requested release does not match any known versions?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `crawl-specs` command that accepts a spec number with or without a dot.
- **FR-002**: The system MUST crawl metadata from 3GPP.org using the spec number redirect flow.
- **FR-003**: The system MUST crawl metadata from whatthespec.net using its JSON API.
- **FR-004**: The system MUST normalize spec numbers to a canonical dotted format for storage and display.
- **FR-005**: The system MUST store spec metadata with source attribution for each record.
- **FR-006**: The system MUST store version lists and available files per source when provided.
- **FR-007**: The system MUST resolve a spec number into a series path and download URL for the latest version.
- **FR-008**: The system MUST provide a `doc-only` option for spec downloads that attempts to retrieve only the `.doc` or `.docx` document from a remote zip.
- **FR-009**: When `doc-only` mode is enabled, the system MUST attempt to identify the document entry using a simple spec-number match heuristic.
- **FR-010**: If doc-only identification or retrieval fails, the system MUST warn and fall back to downloading/extracting the full zip.
- **FR-011**: The system MUST provide a `checkout-spec` command that downloads/extracts one or multiple specs to the checkout folder.
- **FR-012**: The system MUST provide an `open-spec` command that downloads/extracts a single spec and opens the document with the system default application.
- **FR-013**: The system MUST support the `doc-only` option for `checkout-spec` and `open-spec` downloads.
- **FR-014**: The system MUST provide a `release` option for `crawl-specs`, `query-specs`, `checkout-spec`, and `open-spec`.
- **FR-015**: The default release value MUST be `latest`, which resolves to the newest version from metadata.
- **FR-016**: When a non-default release is provided, the system MUST require it to match a parsed metadata version.
- **FR-017**: If a release cannot be determined, the system MUST warn, skip that spec, and continue with remaining items when applicable.
- **FR-018**: The system MUST download the requested spec zip and extract its contents into a checkout folder path derived from the series and spec number.
- **FR-019**: The system MUST record the extracted document path and any attachments associated with that version.
- **FR-020**: The system MUST provide a `query-specs` command to search by spec number, title keyword, working group, and status.
- **FR-021**: The system MUST support querying a spec with multiple source records and expose any differences.
- **FR-022**: The system MUST record crawl and download outcomes, including success or failure, for auditing and troubleshooting.
- **FR-023**: Feature functionality MUST be implemented as a standalone library module before CLI integration.
- **FR-024**: The CLI MUST support text output and a JSON output mode for structured results; errors go to stderr.
- **FR-025**: Unit tests MUST be written, user-approved, and verified failing before implementation begins.
- **FR-026**: Python implementations MUST use `pyproject.toml` with `uv`, include type hints and Google-style docstrings for public code, use `logging` instead of `print`, rely on `pathlib` for file paths, and keep Ruff and Ty checks clean without suppressions unless explicitly approved.

### Key Entities *(include if feature involves data)*

- **Specification**: Canonical spec number, type, status, title, and owning working group.
- **SpecificationSourceRecord**: Source name, source-specific identifiers, retrieved metadata snapshot, and last retrieved timestamp.
- **SpecificationVersion**: Version identifier, associated file name, and source reference.
- **SpecificationDownload**: Download URL, checkout path, extracted document path, and attachment list for a version.

## Assumptions

- Users will provide spec numbers either dotted or undotted, and the system will normalize them for storage.
- 3GPP.org and whatthespec.net are reachable for crawl operations during typical use.
- The catalog is expected to hold at least 10,000 specs without requiring manual partitioning.
- The checkout folder structure mirrors the 3GPP archive series layout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of attempted crawls for known specs return metadata from at least one source.
- **SC-002**: Users can retrieve an exact match for a known spec number in under 2 seconds.
- **SC-003**: For specs present in both sources, users can view per-source differences for titles and versions.
- **SC-004**: The catalog supports querying at least 10,000 stored specs with no user-visible degradation.
- **SC-005**: For known specs with downloadable zips, the document file is extracted into the expected checkout path in at least 95% of attempts.
- **SC-006**: When doc-only mode is enabled, at least 80% of downloads avoid full-zip retrieval while still producing the expected document file.
