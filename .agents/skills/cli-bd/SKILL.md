---
name: cli-bd
description: Issue tracking using bd (beads) CLI with dependency-aware task management, Dolt-powered version control, and AI-optimized workflows
---

# CLI Tool: Issue Tracking with bd (beads)

## Overview

**bd (beads)** is the issue tracking system for this project. Use it for ALL task tracking - do NOT use markdown TODOs, task lists, or other tracking methods.

## Quick Start

### Check for Ready Work

```bash
# Show unblocked issues
bd ready --json

# Show forgotten issues
bd stale --days 30 --json
```

### Create New Issues

```bash
# Basic issue
bd create "Issue title" -t bug|feature|task -p 0-4 --json

# Issue with dependency
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json

# Hierarchical subtask (parent epic)
bd create "Subtask" --parent <epic-id> --json
```

### Search and Manage

```bash
# List open issues by priority
bd list --status open --priority 1 --json

# Show specific issue
bd show <id> --json
```

### Claim and Update

```bash
# Claim issue (mark as in-progress)
bd update <id> --status in_progress --json

# Update priority
bd update bd-42 --priority 1 --json
```

### Complete Work

```bash
bd close bd-42 --reason "Completed" --json
```

### Commit (CRITICAL at end of session!)

```bash
bd vc commit -m "session changes"
```

Commits changes to Dolt immediately. Always run at end of work session.

## Why bd?

- **Dependency-aware**: Track blockers and relationships between issues
- **Git-friendly**: Dolt-powered version control with native sync
- **Agent-optimized**: JSON output, ready work detection, discovered-from links
- **Prevents duplicate tracking systems and confusion**

## Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

## Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

## Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

## Version Control

bd uses Dolt for version control:

- **Commit changes:** `bd vc commit -m "message"`
- **Push to remote:** `bd vc push`
- **Pull from remote:** `bd vc pull`
- Each write auto-commits to Dolt history

## Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Run `bd vc commit -m "session changes"` at end of session
- ✅ Test with `BEADS_DB=/tmp/test.db` (don't create test issues in production)
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

## GitHub Copilot Integration

If using GitHub Copilot, also create `.github/copilot-instructions.md` for automatic instruction loading. Run `bd onboard` to get content.

## MCP Server (Recommended)

If using Claude or MCP-compatible clients, install **beads MCP server**:

```bash
pip install beads-mcp
```

Add to MCP config (e.g., `~/.config/claude/config.json`):

```json
{
  "beads": {
    "command": "beads-mcp",
    "args": []
  }
}
```

Then use `mcp__beads__*` functions instead of CLI commands.

## Managing AI-Generated Planning Documents

AI assistants often create planning and design documents during development:

- PLAN.md, IMPLEMENTATION.md, ARCHITECTURE.md
- DESIGN.md, CODEBASE_SUMMARY.md, INTEGRATION_PLAN.md
- TESTING_GUIDE.md, TECHNICAL_DESIGN.md, and similar files

**Best Practice: Use a dedicated directory for ephemeral files**

Create `temp/history/` directory in project root:

```
temp/history/
```

Store ALL AI-generated planning/design docs in `temp/history/`. Benefits:

- ✅ Clean repository root
- ✅ Clear separation between ephemeral and permanent documentation
- ✅ Easy to exclude from version control if desired
- ✅ Preserves planning history for archeological research
- ✅ Reduces noise when browsing project

Example `.gitignore` entry:

```gitignore
# AI planning documents (ephemeral)
history/
```

## CLI Help

Run `bd <command> --help` to discover all available flags:

```bash
bd create --help    # Shows --parent, --deps, --assignee, etc.
bd update --help    # Shows all update flags
bd list --help      # Shows search and filter flags
```

## Reference

[beads GitHub](https://github.com/steveyegge/beads)
