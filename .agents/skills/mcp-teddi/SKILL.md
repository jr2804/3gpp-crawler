---
name: mcp-teddi
description: MCP usage for ETSI TEDDI (Terms and Definitions Database Interactive) through the teddi-mcp server. Use when querying terms/abbreviations, listing technical bodies, validating technical body codes, or retrieving exact term definitions from Copilot chat tools.
---

# MCP Server: TEDDI

## Overview

TEDDI (Terms and Definitions Database Interactive) contains definitions and abbreviations extracted from publicly available ETSI deliverables.

Important behavior:

- The same term can have multiple definitions.
- Differences can be minor spelling variants or technical-body specific meanings.
- Technical body filters can change results significantly.

## Tooling

Use these teddi MCP tools:

- `mcp_teddi-mcp_search_teddi`
- `mcp_teddi-mcp_get_term_info`
- `mcp_teddi-mcp_list_technical_bodies`

## Recommended Workflow

1. Validate or discover technical body codes first with `list_technical_bodies`.
2. Run `search_teddi` with explicit `search_in` and `search_pattern`.
3. Apply `technical_bodies` filtering only with known valid codes.
4. If the user wants one specific entry, use `get_term_info` for exact lookup.
5. Summarize results with:
   - concise definition,
   - body-specific differences,
   - document references (spec + URL) when available.

## Query Patterns

### General term exploration

Use `search_teddi` with:

- `search_in="both"`
- `search_pattern="exactmatch"` for strict matching
- `search_pattern="alloccurrences"` when exact match returns nothing

### Technical-body constrained search

Use comma-separated body codes, for example:

- `technical_bodies="3gpp,stq"`
- `technical_bodies="etsi,itu"`

If a code is rejected, call `list_technical_bodies` and retry with valid codes.

## Interpretation Guidance

When multiple results are returned:

- Do not collapse distinct definitions into one if wording or scope differs.
- Highlight whether definitions are singular/plural variants (for example, "Simulator" vs "Simulators").
- Mention when a requested body has no match.

When no results are returned:

- Retry with different casing (`HATS` vs `hats`).
- Retry with `alloccurrences`.
- Keep the same technical body filter unless the user asks to broaden scope.

## Output Quality

For explanations, include:

1. A one-line plain-language meaning.
2. Context of use (for example, telecom testing, standards terminology).
3. Differences by technical body.
4. Optional references to source specs from TEDDI response data.
