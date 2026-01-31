# Documentation

## Documentation Requirements

### README.md Structure

- Provide a clear project description and legal disclaimer.
- Document installation instructions using `uv`.
- Include a quick start guide with examples.
- Link to API documentation.
- Describe conformance testing expectations.
- Outline contributing guidelines.

### Code Documentation

- Write Google-style docstrings for all public APIs.
- Provide type hints on all function signatures.
- Add inline comments for complex algorithms.
- Include examples in docstrings where appropriate.
- Write clear and concise docstrings for all functions, classes, and modules using the Google style.
- Include type hints in docstrings for function parameters and return values.
- Use examples in docstrings to illustrate how to use functions and classes.
- Ensure that the code is well-commented to explain complex logic and decisions.

## User Documentation

### Documentation Structure

This repository maintains separate documentation for humans and for coding agents:

1. **docs/QUICK_REFERENCE.md** - Human-facing CLI usage and behavior (examples, flags)
1. **README.md** - Project overview and contributor entry points
1. **docs/agents-md/** - Agent-facing modular implementation and workflow guidance
1. **AGENTS.md** - Table of contents for all agent-facing modular documentation

### Critical Rules

- **AGENTS.md** serves as the central table of contents for all development documentation
- Modular files in `docs/agents-md/` contain specific aspects of development guidelines
- When adding or modifying features, update relevant sections in the appropriate modular files
- Keep documentation consistent with actual implementation

### Documentation Workflow

**When adding/modifying features:**

1. **Implement** feature in code
1. **Update** relevant sections in `docs/agents-md/` modular files
1. **Verify** `AGENTS.md` table of contents remains accurate
1. **Test** that all examples in documentation work correctly
1. **Run** linting and formatting on documentation files

**Example workflow for adding a new feature:**

1. Implement: src/tdoc_crawler/ - add new component
1. Test: tests/ - add corresponding tests
1. Update agent docs: docs/agents-md/ - document new structure/patterns
1. Update human docs (if CLI behavior changed): docs/QUICK_REFERENCE.md
1. Verify: AGENTS.md - table of contents is current

### Documentation Updates

Focus updates on these key areas:

- **3GPP domain/crawling changes** → Use skills in `.config/skills/3gpp/`
- **Architecture changes** → `300_*`
- **Database contract changes** → `320_*`
- **Engineering standards** → `600_*`
- **Testing approaches** → `700_*`

### Cleanup

Any documentation generated during development should be:

- Integrated into appropriate modular files in `docs/agents-md/`
- Removed from project root after integration
- Kept focused and concise without redundant information

______________________________________________________________________

### General Documentation Guidelines

- Use markdown formatting for headings, lists, code blocks, and links
- Use clear and concise language
- Use consistent terminology and naming conventions
- Keep documentation focused on practical guidance for developers
- Ensure all code examples are tested and functional
- Maintain consistency across all modular documentation files
