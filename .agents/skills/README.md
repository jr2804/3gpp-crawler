# 3GPP Skills

Skills for understanding and working with 3GPP data.

## Skills

### @3gpp-basics

General 3GPP organization overview, partnerships, and scope.

### @3gpp-working-groups

Working group nomenclature, tbid/SubTB identifiers, and hierarchy.

### @3gpp-meetings

Meeting structure, naming conventions, and meeting pages.

### @3gpp-tdocs

TDoc patterns, metadata, and FTP/HTTP server access.

### @3gpp-portal-authentication

EOL authentication, AJAX login patterns, and portal data fetching.

### @3gpp-releases

3GPP release structure, versioning, and TSG rounds.

### @3gpp-specifications

TS and TR numbering, spec file formats, and directory structure.

### @3gpp-change-request

Change Request procedure, workflow, status tracking, and CR database.

- [SKILL.md](3gpp-change-request/SKILL.md) - Full CR reference
- [workflow.md](3gpp-change-request/workflow.md) - Quick workflow guide

### @mcp-teddi

MCP usage for TEDDI term and definition search from Copilot chat tools.

### @cli-teddi

CLI usage for teddi-mcp via `uv run` for search, technical body listing, and server mode.

## Cross-Reference Map

| From \\ To | basics | working-groups | meetings | tdocs | portal-auth | releases | specs | change-request |
|-------------------|--------|----------------|----------|-------|-------------|----------|--------|---------------|
| basics | - | X | X | - | X | X | X | X |
| working-groups | X | - | X | - | X | X | X | X |
| meetings | X | X | - | - | X | X | X | X |
| tdocs | X | X | X | - | X | X | X | X |
| portal-auth | X | X | X | - | - | X | X | X |
| releases | X | X | X | - | X | - | X | X |
| specs | X | X | X | - | X | X | - | X |
| change-request | X | X | X | - | X | X | X | - |

## Usage

Use these skills when:

- Implementing features related to 3GPP data crawling
- Understanding 3GPP document and meeting structures
- Parsing TDoc metadata from portal or FTP
- Normalizing working group or subgroup names
- Working with Change Requests and specifications
- Authenticating with 3GPP portal

## Related

- TDoc-Crawler project: AGENTS.md for implementation details
- 3GPP Official: <https://www.3gpp.org/>
