# Updating AGENTS.md - Review and Maintenance Process

## Overview

This document describes the process for reviewing and updating the AGENTS.md file and its modular components. The modular structure allows for maintainable documentation that can be extended as the project evolves.

## File Structure and Numbering System

The documentation uses a numbered system for easy extension and logical organization:

- **0xx series**: General/foundational content and tool usage
- **1xx series**: Project-specific tools and knowledge
- **2xx series**: Project knowledge and architecture
- **3xx series**: Architecture and data structures
- **4xx series**: Data structures and implementation
- **5xx series**: Implementation and development
- **6xx series**: Development and testing
- **7xx series**: Testing and documentation
- **8xx series**: Documentation and maintenance
- **9xx series**: Meta-documentation

### Current Modular Files

- `100_Tool_Usage.md` - Guidelines on using development tools and MCP servers
- `110_Tool_beads.md` - Tool usage: beads issue tracking
- `120_Tool_memorygraph.md` - Tool usage: memory-graph
- `130_Tool_sequential_thinking.md` - Tool usage: sequential-thinking
- `300_Repo_Architecture_and_Key_Files.md` - Repository architecture and "source of truth" map
- `320_Database_Schema_and_Invariants.md` - Database schema contract and invariants
- `600_Engineering_Standards.md` - Engineering standards for agents (workflow, style, constraints)
- `700_Testing_and_Mocking_Patterns.md` - Testing patterns and mocking boundaries
- `800_Documentation.md` - Documentation requirements and guidelines
- `900_Updating_AGENTS.md` - This document (meta-documentation)

### Extension Strategy

The numbering system allows future extensions:

- **120-199**: Additional tool documentation
- **120-199**: Additional project knowledge files
- **210-299**: Additional project knowledge and architecture topics
- **310-399**: Additional architecture and data structure topics
- **410-499**: Additional data structure and implementation topics
- **510-599**: Additional implementation and development topics
- **610-699**: Additional development and testing topics
- **710-799**: Additional testing and documentation topics
- **810-899**: Additional documentation topics
- **910-999**: Additional meta-documentation

## Review Process

### When to Review

After several implementation steps, the AGENTS.md file may need an update. Reviews should be triggered when:

1. **Significant project changes** have been implemented
1. **New patterns or guidelines** have emerged that should be documented
1. **Current documentation becomes inconsistent** with actual implementation
1. **Structural improvements** are needed for better maintainability

### Review Workflow

1. **Preparation**: Review current codebase and documentation
1. **Analysis**: Identify gaps, inconsistencies, and improvement opportunities
1. **Documentation**: Create review findings document
1. **Validation**: Review findings with stakeholders if needed
1. **Implementation**: Apply approved changes to documentation

### Creating Review Findings

When a review is triggered, use the following prompt template:

```markdown
Please review the current code basis and think thoroughly about possible changes/updates/modifications/refactoring/restructuring of the coding instruction file AGENTS.md, which would help coding assistants to (re-)generate the code basis as close as possible.
Document your review findings in the file `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md` (truncate existing content, if applicable), including specific proposed changes with explanations. Avoid copying too many specific source code samples/examples into `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`. Sort and prioritize your findings them based on impact and effort. Perform creating the findings file, perform a Markdown lint pass on it. If your review does not find any necessary changes, simply state that the current AGENTS.md is adequate and requires no modifications.
```

### Review Findings Document Structure

The review findings document should include:

1. **Executive Summary** - Brief overview of identified issues
1. **High Priority Changes** - Critical improvements needing immediate attention
1. **Medium Priority Changes** - Important enhancements for next iteration
1. **Low Priority Changes** - Nice-to-have improvements
1. **Structural Suggestions** - Recommendations for better organization
1. **Content Gaps** - Missing information that should be added

### Prioritization Criteria

- **Impact**: How significantly the change improves coding assistant effectiveness
- **Effort**: How much work is required to implement the change
- **Reusability**: Whether the improvement benefits other projects
- **Maintainability**: How the change affects long-term documentation maintenance

## Update Process

### Applying Changes

After review findings are documented and approved:

1. **Create Backup**: Create a backup of current modular files
1. **Implement Changes**: Apply changes according to prioritization
1. **Update References**: Ensure cross-references between files are updated
1. **Validate Links**: Check that all file references are working
1. **Test Structure**: Verify that the documentation structure is coherent

### Update Workflow Template

When applying changes, use this prompt template:

```markdown
Based on the review findings in the file #file:REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md (`docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`), please update the coding instruction file `AGENTS.md`, or more specifically, the relevant sections within the modular documentation in `docs/agents-md/*.md`. Make sure to incorporate all relevant suggestions in the prioritized order specified by the review document, ensuring that the updated `AGENTS.md` and its modules reflect the best practices and guidelines for coding assistants to (re-)generate the code basis as close as possible.

Avoid copying citing/copying too many source code samples/examples into `AGENTS.MD` or the modular documentation files. You might move the current section regarding "Reviews of AGENTS.md" to a different place (should preferably remain at the very end of the document), but keep its content unchanged. After integration of the review findings, apply a final markdown lint pass and cleanup.
```

## Maintenance Guidelines

### Regular Maintenance

- **Quarterly Reviews**: Schedule reviews every 3-4 months
- **Version Synchronization**: Ensure documentation matches current implementation
- **Consistency Checks**: Verify that all modular files are aligned
- **Link Validation**: Check that all internal references are working

### Continuous Improvement

- **Feedback Collection**: Gather feedback from coding assistants using the documentation
- **Pattern Recognition**: Identify recurring issues or questions
- **Evolution Tracking**: Document how the guidelines evolve over time

### Quality Assurance

- **Markdown Linting**: Apply markdown linting to all documentation files
- **Link Checking**: Validate that all internal links work correctly
- **Content Review**: Ensure accuracy and clarity of all information
- **Version Control**: Commit changes with clear, descriptive messages

## File Naming Conventions

### Review Files

- `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md` - Temporary review document
- `docs/REVIEW_YYYY-MM-DD_<topic>.md` - Specific review sessions

### Update Files

- History files follow the pattern: `docs/history/YYYY-MM-DD_SUMMARY_<NN>_<topic>.md`
- Use descriptive names that clearly indicate the nature of changes
- Include sequential numbers for multiple changes on the same day

## Archive and Cleanup

### Temporary Files

- Review documents should be cleaned up after implementation
- Draft files should not be committed to version control
- Use appropriate `.gitignore` rules for temporary documentation

### Version Control

- **Branching**: Use feature branches for significant documentation changes
- **Commit Messages**: Use clear, descriptive commit messages for documentation updates
- **Tagging**: Consider tagging documentation releases for easy reference

## Integration with Development Workflow

### Coordination with Code Changes

- Documentation updates should be coordinated with code changes
- New features should include relevant documentation updates
- Breaking changes require documentation updates before release

### Training and Onboarding

- **New Contributors**: Use this document as part of onboarding process
- **Reference Material**: Include this document in development guidelines
- **Best Practices**: Incorporate documentation maintenance into development workflow

This meta-documentation ensures that the AGENTS.md documentation system remains current, effective, and aligned with the evolving needs of the project and its contributors.
