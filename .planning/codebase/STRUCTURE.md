# Structure -- 3GPP Crawler

## Top-Level Directory

3gpp-crawler/
|-- src/tdoc_crawler/       # Core library package
|-- tests/                  # Test suite
|-- packages/               # In-repo shared packages (workspace)
|-- docs/                   # Documentation
|-- scripts/                # Utility scripts
|-- .agents/                # Agent configuration
|-- .planning/              # Planning documents
|-- .config/                # Local configuration
|-- .vscode/                # VS Code settings
|-- .venv/                  # Virtual environment (gitignored)
|-- .git/                   # Git repository
|-- pyproject.toml          # Build config, deps, entry points
|-- ruff.toml               # Ruff linter config
|-- AGENTS.md               # Agent instructions (root)
|-- README.md               # Project README
|-- mkdocs.yml              # Documentation site config
|-- tox.ini                 # Tox config
|-- ty.toml                 # Ty tool config
|-- uv.lock                 # Lockfile
|-- .env.example            # Environment variable template
|-- .pre-commit-config.yaml # Pre-commit hooks
|-- codecov.yaml            # Coverage config
|-- LICENSE                 # License file

## Source Tree: src/tdoc_crawler/

### Root Package Files

| File | Purpose |
|------|---------|
| __init__.py | Package version (0.0.1), author metadata |
| __main__.py | Entry point: invokes tdoc_app() from cli module |
| AGENTS.md | Domain-oriented architecture guide, import patterns, data sources table |

### cli/ -- CLI Layer (Thin Typer Wrappers)

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 11 | Exports all CLI apps and load_cli_config |
| AGENTS.md | 37 | CLI design rules: thin layer, no business logic |
| tdoc_app.py | 310 | Main Typer app for TDoc/Meeting commands. Callback registers CacheManager. Commands: crawl, crawl-meetings, query, query-meetings, open, checkout, stats |
| spec_app.py | 59 | Spec-focused Typer app. Commands: crawl, query, checkout, open |
| mgmt_app.py | 64 | Management Typer app. Sub-apps: config, workspace |
| config_app.py | -- | Config subcommands: init, show |
| crawl.py | 457 | Crawl command implementations (crawl_tdocs, crawl_meetings, crawl_specs) |
| query.py | 355 | Query command implementations (query_tdocs, query_meetings, query_specs) |
| args.py | -- | Reusable Annotated[..] type aliases for CLI options (WorkingGroupOption, TDocIdArgument, etc.) |
| printing.py | 333 | Table rendering and output formatting for TDocs, meetings, specs |
| formatting.py | -- | Structured output: TableColumnSpec, print_structured_output, format_output |
| config.py | -- | load_cli_config() -- config file loading at CLI startup |
| _shared.py | -- | Shared: console singleton, create_progress_bar, handle_clear_options |
| _workspace_commands.py | -- | Workspace management Typer commands |
| constants.py | -- | Help panel group constants (HELP_PANEL_MAIN, HELP_PANEL_CRAWLING, HELP_PANEL_QUERY) |
| utils.py | -- | CLI utilities: launch_file() for opening files with system default |

### config/ -- Configuration Management

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 51 | Exports: CacheManager, ThreeGPPConfig, ConfigEnvVar, config sources |
| AGENTS.md | 55 | Config rules: CacheManager singleton, ThreeGPPConfig discovery, path rules |
| settings.py | 309 | ThreeGPPConfig with nested models: PathConfig, HttpConfig, CredentialsConfig, CrawlConfig. Alias TDocCrawlerConfig for backwards compat |
| cache_manager.py | 134 | CacheManager singleton: register/resolve pattern. Defaults: db_file, http_cache_file, checkout_dir, workspace_registry_file, llm_wiki_dir |
| env_vars.py | 74 | ConfigEnvVar StrEnum mapping env vars (TDC_*, HTTP_CACHE_*, TDC_EOL_*) to TOML config paths |
| sources.py | -- | Config file discovery (TOML), loading, and merging logic |
| export.py | -- | Config export/serialization utilities |
| workspace_registry.py | -- | JSON-file-backed workspace registry (wiki build tracking) |

### database/ -- Oxyde ORM Persistence

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 17 | Facade exports: DocDatabase, TDocDatabase, MeetingDatabase, SpecDatabase, DatabaseError |
| oxyde_models.py | 224 | All Oxyde ORM model definitions (9 tables): WorkingGroupRecord, SubWorkingGroupRecord, CrawlLogEntry, MeetingMetadata, TDocMetadata, Specification, SpecificationSourceRecord, SpecificationVersion, SpecificationDownload |
| base.py | 282 | DocDatabase base class: async context manager, table auto-creation, reference data seeding, crawl logging, clear_tables |
| meetings.py | 333 | MeetingDatabase: meeting upsert/query, statistics, meeting ID resolution with fuzzy matching |
| tdocs.py | 329 | TDocDatabase (extends MeetingDatabase): TDoc upsert/bulk_upsert, filtered query with glob patterns (source, title, agenda), get_existing_tdoc_ids |
| specs.py | 531 | SpecDatabase: spec crawling from multiple sources, query with filters, source record/version management |
| errors.py | 15 | DatabaseError class with code+detail pattern and factory method |
| protocols.py | 69 | DatabaseFactory protocol and DefaultDatabaseFactory for DI |

### tdocs/ -- TDoc Domain

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 11 | Package marker, exports TDocStatus. Note: operations not re-exported (circular import prevention) |
| models.py | 277 | TDocMetadata (Pydantic), TDocCrawlConfig, TDocQueryConfig, TDocStatus enum (19 status values) |
| utils.py | -- | TDoc utility functions |
| operations/__init__.py | 45 | Exports: TDocCrawler, TDocCrawlResult, CheckoutResult, fetch_missing_tdocs, fetch_via_whatthespec_batch, checkout_tdoc, etc. |
| operations/crawl.py | 419 | TDocCrawler class: parallel subinterpreter-based crawl orchestration, meeting filtering, deduplication, target filtering, overall timeout |
| operations/fetch.py | -- | fetch_missing_tdocs, fetch_via_whatthespec_batch, create_source, FetchMethod enum, FetchMissingResult |
| operations/checkout.py | -- | checkout_tdoc, checkout_tdocs, checkout_meeting_tdocs, prepare_tdoc_file, CheckoutResult |
| sources/__init__.py | -- | Source package exports |
| sources/base.py | 103 | TDocSource protocol (fetch_by_id, fetch_by_meeting), TDocSourceConfig |
| sources/doclist.py | -- | Excel DocList source (batch, no auth) -- downloads Excel files from 3GPP FTP |
| sources/whatthespec.py | -- | WhatTheSpec API source (single, no auth) |
| sources/portal.py | -- | 3GPP Portal source (single, auth required) |

### meetings/ -- Meeting Domain

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 5 | Package marker |
| models.py | 139 | MeetingMetadata, MeetingCrawlConfig, MeetingQueryConfig (Pydantic models) |
| utils.py | -- | normalize_subgroup_alias, normalize_working_group_alias helpers |
| operations/crawl.py | 225 | MeetingCrawler class: fetches meeting listings from 3GPP portal, handles incremental crawling, EOL auth |
| sources/__init__.py | -- | Meeting sources exports |

### specs/ -- Specification Domain

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 7 | Package marker. Note: avoid eager imports |
| models.py | 143 | Specification, SpecificationSourceRecord, SpecificationVersion, SpecificationDownload, SpecQueryFilters, SpecQueryResult |
| operations/__init__.py | -- | Spec operations exports |
| operations/checkout.py | -- | checkout_spec, checkout_specs, build_default_spec_sources |
| sources/__init__.py | -- | Spec sources exports |
| sources/base.py | 43 | SpecSource protocol, FunctionSpecSource adapter (dataclass wrapping callable as SpecSource) |
| sources/whatthespec.py | -- | WhatTheSpec API spec source |
| sources/threegpp.py | -- | 3GPP official spec pages source |

### extraction/ -- Document Conversion & Extraction

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 53 | Exports: convert_to_pdf, convert_document_to_markdown, fetch_tdoc_files, MetricsTracker, ExtractionProfile |
| conversion.py | 261 | PDF conversion: ConverterBackend enum, convert_to_pdf(), ensure_pdf(), convert_via_libreoffice(), convert_via_remote() |
| convert.py | -- | OpenDataLoader integration: convert_document_to_markdown(), extract_document_structured_from_tdoc() |
| fetch_tdoc.py | -- | Download TDoc files from 3GPP FTP: fetch_tdoc_files(), TDocFiles |
| metrics.py | -- | Performance tracking: MetricsTracker, MetricType, timed_operation, TimedOperationResult |
| profiles.py | -- | ExtractionProfile, DEFAULT_EXTRACTION_PROFILE |
| workspace_utils.py | -- | Workspace-related extraction utilities |
| checkout.py | -- | Extraction checkout utilities |

### workspaces/ -- Workspace Management

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 51 | Exports: create_workspace, list_workspaces, add_workspace_members, checkout_tdoc_to_workspace, etc. |
| crud.py | -- | Workspace CRUD: create, delete, get, list, set_active |
| members.py | -- | Member management: add, remove, deactivate, list, get_counts |
| utils.py | -- | Utility: checkout_tdoc_to_workspace, checkout_spec_to_workspace, resolve_tdoc_checkout_path |

### http_client/ -- HTTP Client

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 23 | Exports: create_cached_session, download_to_file, PoolConfig, resolve_ssl_verify |
| session.py | 321 | hishel-backed cached HTTP session: create_cached_session(), custom CacheAdapter, retry support, concurrency limits |
| protocols.py | 36 | DefaultHttpClientProvider -- reusable session wrapper |

### models/ -- Shared Models & Reference Data

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 41 | Exports: OutputFormat, SortOrder, PortalCredentials, WorkingGroup, WorkingGroupRecord, SubWorkingGroupRecord, CrawlLogEntry |
| base.py | 38 | OutputFormat (TABLE, JSON, ISON, TOON, YAML), SortOrder (ASC, DESC), PortalCredentials dataclass |
| working_groups.py | -- | WorkingGroup enum (RAN, SA, CT), WORKING_GROUP_RECORDS reference data |
| subworking_groups.py | -- | SubWorkingGroupRecord dataclass, SUBTB_INDEX, CODE_INDEX lookup dicts |
| crawl_log.py | -- | CrawlLogEntry model |
| workspaces.py | 190 | Workspace, DocumentClassification, ExtractedTableElement, ExtractedFigureElement, ExtractedEquationElement, SummarizeResult, ConversionError, TDocNotFoundError, WorkspaceNotFoundError, SourceKind enum |

### utils/ -- Shared Utilities

| File | Lines | Purpose |
|------|-------|---------|
| __init__.py | 0 | Empty init |
| async_helpers.py | 37 | run_async() -- safe async-from-sync helper (handles running loop detection) |
| normalization.py | -- | normalize_tdoc_id, normalize_tdoc_ids, normalize_release, normalize_spec_number, normalize_portal_meeting_name |
| parse.py | -- | parse_agenda_item_nbr, parse_spec_version, parse_spec_version_nbr, collect_spec_numbers, parse_working_groups, parse_subgroups |
| date_parser.py | -- | parse_partial_date() -- flexible date parsing (YYYY, YYYY-MM, YYYY-MM-DD) |
| misc.py | -- | utc_now() utility |
| security.py | -- | validate_api_url() for URL safety |

### Supporting Modules

| Module | File | Purpose |
|--------|------|---------|
| constants/__init__.py | -- | Exports URL and pattern constants |
| constants/urls.py | -- | URL templates: PORTAL_BASE_URL, MEETINGS_BASE_URL, TDOC_DOWNLOAD_URL, SPEC_URL_TEMPLATE, BROWSER_HEADERS |
| constants/patterns.py | -- | Regex patterns: TDOC_PATTERN, DATE_PATTERN, EXCLUDED_DIRS, TDOC_SUBDIRS |
| clients/__init__.py | 14 | Exports: PortalClient, PortalAuthenticationError, PortalParsingError |
| clients/portal.py | -- | PortalClient -- authenticated 3GPP portal HTTP client |
| parsers/__init__.py | 13 | Exports: MeetingParser, PortalParser, PortalParsingError, parse_tdoc_portal_page |
| parsers/meetings.py | -- | MeetingParser: parse_meeting_page() for HTML meeting listings |
| parsers/portal.py | -- | PortalParser: parse_tdoc_portal_page() for HTML TDoc details |
| parsers/protocols.py | -- | Parser protocol definitions |
| workers/__init__.py | 9 | Exports: fetch_meeting_document_list_subinterpreter |
| workers/tdoc_worker.py | 60 | Subinterpreter worker: serializes/deserializes TDoc data as JSON for IPC |
| logging/__init__.py | 101 | RichHandler-based logging: get_logger(), set_verbosity(), DEFAULT_LEVEL, configure_logger() |
| credentials.py | 98 | Credential resolution: set_credentials(), resolve_credentials() with cascading resolution (CLI -> Config -> Env -> Prompt) |

## Test Tree: tests/

| File/Dir | Lines | Purpose |
|----------|-------|---------|
| AGENTS.md | 49 | Test conventions, fixtures guide, coverage targets |
| conftest.py | 259 | Shared fixtures: test_cache_dir, test_db_path, sample_tdocs, sample_meetings, populated_db |
| __init__.py | -- | Test package marker |
| .gitignore | -- | Ignore test artifacts |
| data/ | -- | Test data files |
| config/ | -- | Config-specific tests |
| convert_lo/ | -- | Conversion tests |
| pool_executor/ | -- | Pool executor tests |
| teddi_mcp/ | -- | MCP-related tests |
| test_cache_manager.py | -- | CacheManager tests |
| test_checkout.py | -- | Checkout tests |
| test_cli.py | -- | CLI integration tests |
| test_cli_dotenv.py | -- | Dotenv CLI tests |
| test_config_export.py | -- | Config export tests |
| test_crawler.py | -- | Crawler tests |
| test_credentials.py | -- | Credential resolution tests |
| test_database.py | -- | Database operation tests |
| test_formatting.py | -- | Formatting tests |
| test_graph_errors.py | -- | Graph error handling tests |
| test_http_client.py | -- | HTTP client tests |
| test_meeting_document_list.py | -- | Meeting document list tests |
| test_models.py | -- | Model validation tests |
| test_new_cli_flags.py | -- | New CLI flag tests |
| test_normalization.py | -- | Normalization tests |
| test_portal_auth.py | -- | Portal auth tests |
| test_portal_client.py | -- | Portal client tests |
| test_specs_cli.py | -- | Spec CLI tests |
| test_specs_database.py | -- | Spec DB tests |
| test_specs_downloads.py | -- | Spec download tests |
| test_specs_normalization.py | -- | Spec normalization tests |
| test_specs_sources.py | -- | Spec source tests |
| test_targeted_fetch.py | -- | Targeted fetch tests |
| test_whatthespec.py | -- | WhatTheSpec tests |
| test_workspaces.py | -- | Workspace tests |

## Entry Points Summary

### CLI Entry Points (pyproject.toml)

- tdoc-crawler -> tdoc_app:tdoc_app (main TDoc/Meeting CLI)
- spec-crawler -> spec_app:spec_app (Spec-only CLI)
- 3gpp-crawler -> mgmt_app:mgmt_app (Management CLI)

### Python Entry Points

- python -m tdoc_crawler -> __main__.py -> cli.tdoc_app.tdoc_app()

### Key Constructor / Entry Classes

- TDocCrawler (tdocs/operations/crawl.py): Crawl orchestrator
- MeetingCrawler (meetings/operations/crawl.py): Meeting crawl orchestrator
- TDocDatabase (database/tdocs.py): TDoc + Meeting DB operations
- MeetingDatabase (database/meetings.py): Meeting DB operations
- SpecDatabase (database/specs.py): Spec DB + crawl operations
- DocDatabase (database/base.py): Base async DB lifecycle
- CacheManager (config/cache_manager.py): Runtime path resolution
- ThreeGPPConfig (config/settings.py): Type-safe configuration
- PortalClient (clients/portal.py): Authenticated portal access
- MeetingParser, PortalParser (parsers/): HTML parsing
- Workspace (models/workspaces.py): Workspace data model
