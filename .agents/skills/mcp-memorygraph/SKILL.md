---
name: mcp-memorygraph
description: Store and recall project-specific context, decisions, and patterns across coding sessions using Memory-Graph
---

# Memory Protocol (Memory-Graph)

**If MCP server `memorygraph` is available**, use it to store and retrieve project context automatically.

## REQUIRED: Before Starting Work

You MUST use `recall_memories` before any task to avoid repeating work.

```python
recall_memories(query="tdoc-crawler crawling and database patterns")
```

## REQUIRED: Automatic Storage Triggers

Store memories on ANY of:

- **Git commit** → What was fixed/added
- **Bug fix** → Problem + solution
- **Version release** → Summarize changes
- **Architecture decision** → Choice + rationale
- **Pattern discovered** → Reusable approach

## Timing Mode

```python
memory_mode: "immediate" | "on-commit" | "session-end"
```

- **immediate**: Store immediately after action
- **on-commit**: Trigger on git commits (default)
- **session-end**: Store at end of coding session

## Memory Fields

```python
{
  "type": "solution" | "problem" | "code_pattern" | "fix" | "error" | "workflow",
  "title": "Specific, searchable (not generic)",
  "content": "Accomplishment, decisions, patterns",
  "tags": ["project", "tech", "category"],  # REQUIRED
  "importance": 0.8,  # Critical (0.8+), Standard (0.5-0.7), Minor (0.3-0.4)
  "relationships": []  # Link related memories when they exist
}
```

## Tag Guidelines

Tags are REQUIRED for effective retrieval:

- **project**: Project name or identifier
- **tech**: Technology stack component (e.g., "pydantic", "sqlite", "pytest")
- **category**: Type of memory (e.g., "database", "authentication", "testing")

## Best Practices

- **Don't wait to be asked**: Memory storage is automatic
- **Be specific**: Titles should be searchable, not generic
- **Link related memories**: Connect related decisions/patterns
- **Use proper type**: Choose correct type for each memory
- **Set appropriate importance**: Help prioritize retrieval

## Query Examples

```python
# Recall by project
recall_memories(query="tdoc-crawler database")

# Recall by technology
recall_memories(query="pydantic models")

# Recall by pattern
recall_memories(query="caching patterns")

# Recall by specific task
recall_memories(query="TDoc authentication")
```

## References

- [Memory-Graph GitHub](https://github.com/gregorydickson/memory-graph)
