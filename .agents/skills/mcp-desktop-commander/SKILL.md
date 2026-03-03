---
name: mcp-desktop-commander
description: File system operations, process management, terminal interaction, and workspace exploration
---

# Desktop Commander

**If MCP server `desktop-commander` is available**, use this tool for file system and terminal operations.

## When to Use

Use desktop-commander for:

- **File system operations**: Create, edit, read directories and files
- **Process management**: Start, stop, and manage terminal processes
- **Search operations**: Search files and content efficiently
- **Workspace exploration**: Navigate and understand workspace structure
- **Terminal interaction**: Execute shell commands and scripts

## Key Capabilities

### File Operations

```python
# List directory contents
list_directory(path, depth=2)

# Read files
read_file(path, offset=0, length=100)

# Write files
write_file(path, content, mode="rewrite" | "append")

# Create directories
create_directory(path)
```

### Process Operations

```python
# Start process
start_process(command, timeout_ms=120000, shell="powershell")

# Read process output
read_process_output(pid, offset=0, length=100)

# Send input to process
interact_with_process(pid, input="command", timeout_ms=8000)

# Terminate process
force_terminate(pid)
```

### Search Operations

```python
# Start file search
start_search(path, pattern, search_type="files" | "content")

# Get search results
get_more_search_results(session_id, offset=0, length=100)

# Stop search
stop_search(session_id)
```

## Best Practices

- **Use for file operations**: Prefer desktop-commander over manual shell commands
- **Batch operations**: Use read_multiple_files for multiple files
- **Error handling**: Handle file permissions and path errors gracefully
- **Process management**: Always terminate processes when done
- **Search efficiently**: Use appropriate search_type for your needs

## References

- [Desktop Commander](https://github.com/wonderwhy-er/DesktopCommanderMCP)
