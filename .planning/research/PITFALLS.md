# Domain Pitfalls

Domain: 3GPP standards-document corpora migration from traditional RAG to Karpathy-style LLM Wiki compilation
Researched: 2026-04-27
Overall confidence: MEDIUM

## Critical Pitfalls

### Pitfall 1: Citation Drift During Wiki Compilation
What goes wrong:
LLM-generated wiki pages summarize correctly at paragraph level but lose deterministic source anchors at clause/table/figure granularity.

Why it happens:
Traditional RAG systems often cite chunk IDs, while wiki synthesis introduces cross-document abstraction that can dissolve exact provenance unless forced by schema.

Consequences:
- unverifiable statements in standards-sensitive workflows
- weak auditability for "why this answer" in compliance or engineering review
- inability to trace claims back to exact TS/TR versions

Prevention:
- require every generated claim to carry document_id, version, page, and span references
- compile wiki entries from deterministic extraction JSON, not markdown-only text
- enforce a no-citation/no-publish rule in the wiki build step

Detection:
- citation coverage below threshold (for example under 98%)
- references that resolve to document but not to clause/span
- frequent human reviewer notes such as "cannot verify"

### Pitfall 2: Version Mixing Across Releases and CR States
What goes wrong:
The wiki blends content from multiple 3GPP releases or pre/post-CR states into one canonical statement.

Why it happens:
Standards corpora are highly versioned and parallelized; naive document aggregation ignores release tags, meeting rounds, and change-request lineage.

Consequences:
- contradictory requirements in the same wiki topic
- incorrect downstream guidance for implementation teams
- hidden regressions when newer text silently overrides frozen behavior

Prevention:
- include release, spec version, and meeting/CR lineage in extraction metadata and index keys
- generate release-scoped wiki snapshots first, then explicitly merge with conflict markers
- add deterministic tie-break rules for recency versus normative precedence

Detection:
- same concept mapped to conflicting normative verbs (shall/should/may)
- multiple answers for identical query under same declared release scope
- unexplained jumps in policy text after corpus refresh

### Pitfall 3: Normative Language Flattening
What goes wrong:
The wiki normalizes tone and accidentally weakens normative intent, converting strict requirements into descriptive prose.

Why it happens:
Generative summarization rewards readability and compression, but standards interpretation depends on preserving modality and conditions exactly.

Consequences:
- false compliance assumptions
- implementation bugs from softened requirements
- legal and certification risk in downstream usage

Prevention:
- extract and persist normative markers (shall/shall not/should/may) as structured fields
- render wiki sections with explicit "Normative" versus "Informative" partitions
- add automatic checks that forbid modality downgrades during synthesis

Detection:
- mismatch rate between source modality and wiki modality
- increase in unresolved "is this mandatory" reviewer questions
- high edit churn in normative sections after manual review

### Pitfall 4: Determinism Loss in Build Pipeline
What goes wrong:
Two runs over the same corpus produce materially different wiki pages, embeddings, or graph edges.

Why it happens:
Model sampling, non-pinned dependencies, non-stable chunk ordering, and asynchronous ingestion race conditions create non-reproducible artifacts.

Consequences:
- impossible regression debugging
- flaky evaluation baselines
- low trust in migration quality signals

Prevention:
- pin model versions and extraction dependencies
- disable stochastic generation in compile stages that define canonical wiki text
- enforce stable ordering keys and content hashing for each intermediate artifact
- store deterministic build manifests with input/output checksums

Detection:
- hash diffs between same-input runs
- large semantic delta with no corpus changes
- non-repeatable benchmark outcomes

## Moderate Pitfalls

### Pitfall 5: Table and Formula Semantics Collapse
What goes wrong:
Critical constraints from tabular cells, footnotes, and formulas are dropped or rewritten ambiguously in wiki prose.

Prevention:
- preserve table cell coordinates, header lineage, and footnote references in extraction output
- include formula normalization plus source rendering references
- require targeted table/formula fidelity tests before promoting a wiki build

### Pitfall 6: Over-Aggressive Deduplication of Near-Duplicate Clauses
What goes wrong:
Dedup logic merges clauses that appear similar but differ by release, scenario, or conditional scope.

Prevention:
- deduplicate only within strict scope keys (spec_id + version + clause lineage)
- use semantic similarity as a hint, never as an automatic merge decision
- flag high-similarity cross-version items for explicit adjudication

### Pitfall 7: Query-Time Determinism Broken by Hybrid Retrieval Fallbacks
What goes wrong:
The system claims deterministic extraction-backed answers, but query path silently falls back to legacy vector chunks with weaker provenance.

Prevention:
- separate legacy and wiki retrieval modes at API boundary
- expose provenance mode in every response payload
- block fallback in strict compliance mode

## Minor Pitfalls

### Pitfall 8: Evaluation Set Not Representative of Standards Edge Cases
What goes wrong:
Migration appears successful on generic Q&A tests but fails on annexes, exception clauses, and conditional procedures.

Prevention:
- curate benchmark sets for normative conflicts, cross-reference chains, and release deltas
- include deterministic extraction quality metrics alongside answer quality metrics

### Pitfall 9: Human Review Workflow Too Late in Pipeline
What goes wrong:
Experts only review final wiki pages, when fixing errors is costly and root-cause attribution is hard.

Prevention:
- add review checkpoints at extraction schema validation and wiki pre-publish diff stages
- provide reviewer tools that jump directly from wiki sentence to source span

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Corpus normalization | Version mixing | Release-scoped canonical IDs and lineage fields |
| Deterministic extraction | Build nondeterminism | Stable ordering, pinned models, checksums |
| Wiki compilation | Citation drift | Mandatory span-level citations and publish gates |
| Query integration | Hidden legacy fallback | Explicit retrieval mode contracts |
| Validation | False confidence from weak tests | Standards-specific benchmark suite |

## Sources

- 3GPP series and versioning context (official): https://www.3gpp.org/specifications-technologies/specifications-by-series
- Workspace guidance for 3gpp-ai extraction/storage architecture: packages/3gpp-ai/AGENTS.md
- Workspace global guidance on configuration/path determinism: AGENTS.md
