# Review and Improvements for AGENTS.md

This document outlines proposed changes to `AGENTS.md` to ensure it accurately reflects the current codebase and provides clearer instructions for AI assistants. The findings are prioritized based on their impact.

---

## 1. Update CLI Command Signatures and Descriptions

**Impact:** High

**Problem:** The CLI command signatures in `AGENTS.md` are significantly outdated compared to the implementation in `src/tdoc_crawler/cli/app.py`. This is the most critical issue as it leads to incorrect code generation for the CLI.

**Proposed Changes:**

- **`crawl-tdocs`**: Update the signature to include `incremental`, `verbose`, `workers`, `max_retries`, and `timeout`. Correct the types and default values for existing parameters.
- **`crawl-meetings`**: Update the signature to include `incremental`, `verbose`, `max_retries`, `timeout`, `eol_username`, `eol_password`, and `prompt_credentials`.
- **`query-tdocs`**: Reflect that `tdoc_ids` is optional. Add the new parameters: `limit`, `order`, `start_date`, `end_date`, and `no_fetch`.
- **`open` command**: Rename to `open_tdoc` to match the implementation.
- **`stats` command**: Document the `stats` command as one of the main commands.
- **Command Aliases**: The `AGENTS.md` file correctly mentions the aliases, but the main command definitions should be accurate.

---

## 2. Correct Default Values

**Impact:** High

**Problem:** The default value for `cache_dir` is documented as `./cache`, but the code in `app.py` uses `Path.home() / ".tdoc-crawler"`. This inconsistency can cause confusion and incorrect behavior.

**Proposed Change:**

- Update the "Default Values" table in `AGENTS.md` to show `~/.tdoc-crawler` (or the platform-agnostic equivalent) as the default for `cache_dir`.

---

## 3. Complete Helper Function Documentation

**Impact:** Medium

**Problem:** The "Helper Functions" section in `AGENTS.md` is missing several important functions that are used in the CLI application.

**Proposed Change:**

- Add the following functions to the list of helpers:
  - `launch_file`: To open a file with the default application.
  - `prepare_tdoc_file`: For handling the download and extraction of TDocs.
  - `build_limits`: For creating the `CrawlLimits` object.

---

## 4. Enhance Implementation Pattern Examples

**Impact:** Medium

**Problem:** Several code snippets for implementation patterns are incomplete, using `...` which makes them less useful for an assistant.

**Proposed Changes:**

- **Fuzzy Meeting Name Matching**: Provide a more complete, yet still summarized, implementation for `_normalize_portal_meeting_name` and `_resolve_meeting_id`.
- **Subdirectory Detection**: Flesh out the `_crawl_meeting` code snippet to better illustrate the logic for finding and crawling subdirectories.

---

## 5. Clarify Python-Specific Guidelines

**Impact:** Low

**Problem:** Some of the Python-specific guidelines are either violated by the current code or could be clearer.

**Proposed Changes:**

- **File Size Limits**: Acknowledge that `src/tdoc_crawler/cli/app.py` is an exception to the 250-line limit for modules, and explain that this is acceptable for a main CLI file with many command definitions.
- **Type Checking**: The document correctly states to use `ty` and not `mypy`. This is consistent and should be maintained. No change is needed, but it's worth noting its correctness.

---

## 6. Database Schema Documentation

**Impact:** Low

**Problem:** The database schema section is good but could be slightly more detailed.

**Proposed Change:**

- Briefly expand on the purpose of the `crawl_log` table to make its role in statistics and diagnostics clearer.
