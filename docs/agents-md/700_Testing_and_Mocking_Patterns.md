# Testing and Mocking Patterns (Agent Notes)

This document describes the required testing patterns for safe refactors.

## Test framework

- Use `pytest`.
- Prefer small unit tests, then add integration-style tests when necessary.

## Standard test cache/db locations

Use these paths when tests need an explicit cache/db location:

- Cache directory: `./tests/test-cache`
- Database file: `./tests/test-cache/tdoc_crawler.db`

## Foreign key preparation (critical)

The `tdocs.meeting_id` foreign key must be satisfied.

Rule:

- Always insert/upsert meetings before inserting/upserting TDocs.

This affects both production code and tests.

## Mocking HTTP

When testing crawlers, mock HTTP at the correct import location.

Rule of thumb:

- Patch `requests.Session` in the module that constructs or uses it.

For the TDoc crawler, the conventional patch location is:

- `tdoc_crawler.crawlers.tdocs.requests.Session`

Use BeautifulSoup-parseable HTML in mock responses.

## Portal authentication tests

Tests must not require real ETSI credentials.

- Use environment variables only for local manual runs, not for CI.
- Prefer mocking portal requests for deterministic test behavior.

## How to run

- Run all tests: `uv run pytest -v`
- Run one file: `uv run pytest tests/test_database.py -v`

## Related docs

- DB invariants: [docs/agents-md/320_Database_Schema_and_Invariants.md](320_Database_Schema_and_Invariants.md)
