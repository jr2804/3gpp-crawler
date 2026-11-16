---
title: API Reference
---

The Python API mirrors the CLI: the same core-library functions back both.

## Package overview

::: tdoc_crawler

## TDoc operations

Main-file selection, `open`, and re-classification are shared by CLI and MCP.

::: tdoc_crawler.tdocs.operations

## Main-file overrides

Stored overrides (user-owned) and classification records (computed memory).

::: tdoc_crawler.database.main_files

## Tag operations

Shared by CLI and MCP — AND-of-ORs tag expressions.

::: tdoc_crawler.database.tags

## Configuration

::: tdoc_crawler.config.settings

## HTTP client

::: tdoc_crawler.http_client
