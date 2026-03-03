---
name: mcp-context7
description: Automatic documentation and library API discovery using Context7 MCP server
---

# Context7 - Automatic Documentation

**If MCP server `context7` is available**, always use it when generating code, setup steps, or library/API documentation.

## When to Use

Use context7 for:

- **Generated code examples**: Any code, configuration, or implementation steps
- **Library API documentation**: Resolve library IDs and get docs automatically
- **Setup instructions**: Installation, configuration, or initialization steps
- **Tool integration**: How to use tools together

## Library API Discovery

When working with a library:

1. **Context7 will automatically**: Identify the library and its usage
2. **Fetch documentation**: Get relevant API docs without you asking explicitly
3. **Provide examples**: Show how to use the library in this project's context

## Example Workflow

When you need to work with a library:

```
1. Mention the library name
2. Context7 resolves library ID
3. Fetches API documentation
4. Provides usage examples
5. You write code using the library
```

## Best Practices

- **Let context7 work**: Don't try to manually resolve library docs
- **Use in context**: Allow context7 to provide project-specific examples
- **Verify examples**: Ensure provided examples work in your project's context

## References

- [Upstash Context7](https://github.com/upstash/context7)
