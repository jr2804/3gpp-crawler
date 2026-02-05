# Research

## Decision: Dual-source metadata ingestion

- Decision: Use 3GPP.org redirect-to-details pages and whatthespec.net JSON API as authoritative metadata sources.
- Rationale: The 3GPP portal provides official metadata, while whatthespec.net offers fast JSON access to versions and files; both are needed for coverage and cross-checking.
- Alternatives considered: Single-source ingestion (rejected due to incomplete coverage and missing fields in one source).

## Decision: Release selection behavior

- Decision: Support a `release` option with default `latest`; when a non-default value is provided, it must match metadata versions, otherwise warn and skip.
- Rationale: Aligns CLI behavior with user intent while avoiding ambiguous or invalid downloads.
- Alternatives considered: Implicit nearest-match or silent fallback (rejected due to unexpected results).

## Decision: Doc-only download strategy

- Decision: Use `zipinspect` to list remote zip entries and download only the matching `.doc` or `.docx` file when doc-only is enabled.
- Rationale: Large specs can be multiple gigabytes; doc-only reduces bandwidth and time for most workflows.
- Alternatives considered: Always downloading full zips (rejected due to size) or requiring full extraction (rejected due to performance).

## Decision: Checkout path structure

- Decision: Mirror the 3GPP archive structure under the checkout directory.
- Rationale: Predictable paths match upstream layout and align with existing user expectations for TDoc checkouts.
- Alternatives considered: Flattened or custom paths (rejected due to loss of context and ambiguity).
