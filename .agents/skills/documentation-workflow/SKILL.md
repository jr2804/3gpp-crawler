---
name: documentation-workflow
description: Documentation workflow, structure, and best practices for maintaining project documentation. Use when creating, updating, or refactoring documentation.
---

# Documentation Workflow

## Overview

This skill defines the workflow for maintaining project documentation across multiple audiences (humans and AI coding assistants) and ensuring consistency between code and documentation.

## Documentation Structure

This repository maintains separate documentation for humans and for coding agents:

1. **docs/index.md** - Main documentation entry point (Jekyll-ready)
2. **docs/*.md** - Modular task-oriented user guides (crawl, query, utils, etc.)
3. **README.md** - Project overview and contributor entry points
4. **docs/agents-md/** - Agent-facing modular implementation and workflow guidance
5. **AGENTS.md** - Core guidelines and rules for coding assistants (standalone context)

## Critical Rules

- The modular user documentation in `docs/` **MUST** always be up to date and reflect current CLI behavior
- **AGENTS.md** serves as the primary rule set and context for AI assistants
- When adding or modifying features, update relevant sections in both user docs (`docs/*.md`) and agent docs (`docs/agents-md/`)
- Keep documentation consistent with actual implementation

## Documentation Workflow

### When Adding/Modifying Features

1. **Implement** feature in code
2. **Update** relevant sections in `docs/agents-md/` modular files
3. **Verify** `AGENTS.md` table of contents remains accurate
4. **Test** that all examples in documentation work correctly
5. **Run** linting and formatting on documentation files

### Example Workflow for Adding a New Feature

1. Implement: `src/tdoc_crawler/` - add new component
2. Test: `tests/` - add corresponding tests
3. Update agent docs: `docs/agents-md/` - document new structure/patterns
4. Update human docs (if CLI behavior changed): `docs/QUICK_REFERENCE.md`
5. Verify: `AGENTS.md` - table of contents is current

## Documentation Updates

Focus updates on these key areas:

- **3GPP domain/crawling changes** → Use skills in `.config/skills/3gpp/`
- **Architecture changes** → `docs/agents-md/300_*`
- **Database contract changes** → `docs/agents-md/320_*`
- **Engineering standards** → `docs/agents-md/600_*`
- **Testing approaches** → `docs/agents-md/700_*`

## Documentation Cleanup

Any documentation generated during development should be:

- Integrated into appropriate modular files in `docs/agents-md/`
- Removed from project root after integration
- Kept focused and concise without redundant information

## General Documentation Guidelines

- Use markdown formatting for headings, lists, code blocks, and links
- Use clear and concise language
- Use consistent terminology and naming conventions
- Keep documentation focused on practical guidance for developers
- Ensure all code examples are tested and functional
- Maintain consistency across all modular documentation files

## References

- Jekyll documentation site: https://jekyllrb.com/
- Markdown guide: https://www.markdownguide.org/
