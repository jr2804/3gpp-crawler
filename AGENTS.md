# TDoc-Crawler

CLI tool for querying structured 3GPP TDoc data.

## Commands

```bash
uv run pytest -v           # Run tests
ruff check src/ tests/     # Lint
uv add <package>           # Add dependency
```

## Critical Constraints

- **NEVER** suppress linter issues with `# noqa` in `src/` or `tests/`
- **MUST NOT introduce:** `PLC0415`, `ANN001`, `E402`, `ANN201`, `ANN202`
- Use `uv run` for all Python commands
- `.env` files **MUST NOT** be committed
- **Never** run `git commit` or `git push` autonomously

## Code Style

- Type hints mandatory (`T | None` not `Optional[T]`)
- Use `is`/`is not` for `None` comparisons
- `logging` over `print()`
- Explain **WHY**, not WHAT

## Documentation

- **Skills:** `docs/skills-reference.md`
- **Testing:** `tests/AGENTS.md`
- **Packages:** See respective `AGENTS.md` files

## Packages

| Location | Purpose |
|----------|---------|
| `src/tdoc_crawler/` | Core crawler library |
| `src/tdoc_crawler/cli/` | CLI patterns |
| `packages/tdoc-ai/` | AI document processing |
| `packages/teddi-mcp/` | ~~TEDDI MCP server~~ (moved to separate repo) |
| `packages/convert-lo/` | LibreOffice conversion |
