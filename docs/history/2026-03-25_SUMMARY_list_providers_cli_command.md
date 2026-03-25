# 3gpp-ai List-Providers Feature

**Date:** 2026-03-25
**Status:** Complete

## Overview

Added a new CLI command `3gpp-ai providers list` to the `3gpp-ai` package that displays all supported AI providers for document processing and querying operations.

## Features

- `providers list` command with 4 output formats: table (default), JSON, YAML, TOON
- Shows provider capabilities (LLM, Embedding)
- Aliases with base URLs shown as first-class usable providers (openrouter, nvidia, zai-coding-plan)

## Technical Changes

### `packages/3gpp-ai/threegpp_ai/lightrag/rag.py`
- Added `ProviderAlias` dataclass with `canonical` and `base_url` fields
- Extended `PROVIDER_ALIASES` to `dict[str, ProviderAlias]` with base URL support
- Updated `_resolve_provider()` to handle the new structure

### `packages/3gpp-ai/threegpp_ai/cli.py`
- Added `providers_app = typer.Typer(...)` subcommand
- Implemented `providers_list` command with all output formats

## Providers Supported

| Provider | LLM | Embedding | Via / Base URL |
|----------|-----|-----------|----------------|
| hf | Y | Y | - |
| jina | N | Y | - |
| ollama | Y | Y | - |
| openrouter | Y | Y | via openai - https://openrouter.ai/api/v1 |
| nvidia | Y | Y | via openai - https://integrate.api.nvidia.com/v1/ |
| openai | Y | Y | - |
| zai-coding-plan | Y | Y | via zhipu - https://api.z.ai/api/paas/v4 |
| zhipu | Y | Y | - |

## Requirements

- LIST-01: Add `providers` Typer subcommand ✓
- LIST-02: Provider listing command ✓
- LIST-03: Output format option ✓
- LIST-04: Provider metadata (aliases, capabilities) ✓
