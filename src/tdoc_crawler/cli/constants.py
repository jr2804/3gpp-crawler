"""Shared constants for the CLI."""

HELP_PANEL_MAIN = "Main Commands"
HELP_PANEL_CRAWLING = "Crawling Commands"
HELP_PANEL_QUERY = "Query Commands"
HELP_PANEL_CONFIG = "Configuration Commands"

# Section help text mapping
SECTION_DESCRIPTIONS = {
    "path": "File system paths (cache_dir, db_file, checkout_dir)",
    "http": "HTTP client settings (timeout, retries, caching, SSL)",
    "credentials": "ETSI Online portal credentials (username, password)",
    "crawl": "Crawling filters and limits (working_group, date range, workers)",
}
