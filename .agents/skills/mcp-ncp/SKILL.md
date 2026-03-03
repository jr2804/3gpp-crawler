---
name: mcp-ncp
description: Tool discovery and delegation to appropriate MCP servers based on task analysis
---

# NCP (Natural Context Protocol)

**If MCP server `ncp` is available**, use it to discover the most suitable tools and MCP servers for your current task.

## When to Use

Use ncp BEFORE starting significant work to:

- Analyze task description
- Suggest appropriate tools
- Delegate to MCP servers
- Find optimal solutions

## Workflow

1. **Provide task**: Describe what you need to do
2. **Get recommendations**: ncp analyzes and suggests tools
3. **Follow delegation**: ncp may delegate to other MCP servers
4. **Execute solution**: Use the recommended tool/server

## Example

When you need to analyze a problem:

```python
# Describe your task
"I need to analyze test failures in the pytest suite"

# NCP may suggest:
# - pytest analysis tools
# - debugging MCP servers
# - test visualization tools
```

## Best Practices

- **Use before starting**: Discover tools before beginning work
- **Follow recommendations**: Trust ncp's analysis for tool selection
- **Consider context**: ncp considers available MCP servers

## References

- [NCP GitHub](https://github.com/porfell-dev/ncp)
