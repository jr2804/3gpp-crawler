# CLI Contract: AI Document Processing

**Date**: 2026-02-24
**Module**: `tdoc_crawler.cli.ai`

## Command Group: `ai`

Registered as a Typer sub-app on the main `app` in `cli/app.py`:

```python
ai_app = typer.Typer(help="AI document processing commands")
app.add_typer(ai_app, name="ai", rich_help_panel="AI Commands")
```

## Commands

### `ai process`

Process TDocs through the AI pipeline.

```
tdoc-crawler ai process [--tdoc-id <ID>] [--all] [--new-only] [--json] [--cache-dir <PATH>]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--tdoc-id` | str | None | Process a single TDoc |
| `--all` | bool | False | Process all TDocs |
| `--new-only` | bool | False | Only process unprocessed TDocs (requires `--all`) |
| `--json` | bool | False | Output JSON instead of Rich text |
| `--cache-dir` | Path | None | Override cache directory |

**Text output**: Progress bar per TDoc, final summary line.
**JSON output**: `[{"tdoc_id": "...", "stages": {"classifying": "completed", ...}}]`
**Errors**: Stderr; exit code 1.

### `ai status`

Show processing status for TDocs.

```
tdoc-crawler ai status [--tdoc-id <ID>] [--json] [--cache-dir <PATH>]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--tdoc-id` | str | None | Status for a single TDoc (if omitted, shows all) |
| `--json` | bool | False | Output JSON |
| `--cache-dir` | Path | None | Override cache directory |

**Text output**: Rich table with columns: TDoc ID, Stage, Classified, Extracted,
Embedded, Summarized, Graphed, Error.
**JSON output**: `{"tdoc_id": "...", "current_stage": "...", "classified_at": "...", ...}`

### `ai query`

Semantic search over processed TDocs.

```
tdoc-crawler ai query "<question>" [--tdoc-id <ID>] [--top-k <N>] [--json] [--cache-dir <PATH>]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `<question>` | str | required | Natural language query |
| `--tdoc-id` | str | None | Limit search to a single TDoc |
| `--top-k` | int | 5 | Number of results |
| `--json` | bool | False | Output JSON |
| `--cache-dir` | Path | None | Override cache directory |

**Text output**: Numbered list of matching chunks with TDoc ID, section, and snippet.
**JSON output**: `{"results": [{"tdoc_id": "...", "section": "...", "text": "...", "score": 0.85}]}`

### `ai graph`

Query the temporal knowledge graph.

```
tdoc-crawler ai graph --query "<question>" [--from <DATE>] [--to <DATE>] [--json] [--cache-dir <PATH>]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` | str | required | Natural language graph query |
| `--from` | str | None | Start date filter (ISO format) |
| `--to` | str | None | End date filter (ISO format) |
| `--json` | bool | False | Output JSON |
| `--cache-dir` | Path | None | Override cache directory |

**Text output**: Chronologically ordered answer with TDoc references and meeting context.
**JSON output**: `{"answer": "...", "nodes": [...], "edges": [...]}`

## Separation of Concerns

All CLI functions in `cli/ai.py` follow the delegation pattern:

1. Parse Typer arguments
1. Initialize `CacheManager` and `AiConfig`
1. Call the library function from `tdoc_crawler.ai`
1. Format output (Rich table or JSON) and print via `typer.echo`

No domain logic in the CLI module.
