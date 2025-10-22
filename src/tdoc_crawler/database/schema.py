"""Database schema initialization and configuration."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1


def configure_connection(conn: sqlite3.Connection) -> None:
    """Configure SQLite connection with optimal settings."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema with all required tables and reference data."""
    # Schema metadata table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (id, schema_version) VALUES (1, ?)",
        (SCHEMA_VERSION,),
    )

    # Working groups table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS working_groups (
            tbid INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            ftp_identifier TEXT NOT NULL
        )
        """
    )

    # Subworking groups table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subworking_groups (
            subtb INTEGER PRIMARY KEY,
            tbid INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (tbid) REFERENCES working_groups(tbid),
            UNIQUE (tbid, code)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_swg_tbid ON subworking_groups(tbid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_swg_code ON subworking_groups(code)")

    # Meetings table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meetings (
            meeting_id INTEGER PRIMARY KEY,
            tbid INTEGER NOT NULL,
            subtb INTEGER NOT NULL,
            short_name TEXT NOT NULL,
            title TEXT,
            start_date TEXT,
            end_date TEXT,
            location TEXT,
            files_url TEXT,
            portal_url TEXT,
            last_synced TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (tbid) REFERENCES working_groups(tbid),
            FOREIGN KEY (subtb) REFERENCES subworking_groups(subtb)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_meetings_tbid ON meetings(tbid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_meetings_subtb ON meetings(subtb)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_meetings_dates ON meetings(start_date, end_date)")

    # TDocs table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tdocs (
            tdoc_id TEXT PRIMARY KEY COLLATE NOCASE,
            url TEXT NOT NULL,
            working_group TEXT NOT NULL,
            subgroup TEXT NOT NULL,
            meeting TEXT,
            meeting_id INTEGER,
            file_size INTEGER,
            title TEXT,
            contact TEXT,
            tdoc_type TEXT,
            for_purpose TEXT,
            agenda_item TEXT,
            status TEXT,
            is_revision_of TEXT COLLATE NOCASE,
            document_type TEXT,
            checksum TEXT,
            source_path TEXT,
            date_created TEXT,
            date_retrieved TEXT NOT NULL,
            date_updated TEXT NOT NULL,
            validated INTEGER NOT NULL DEFAULT 0,
            validation_failed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id),
            FOREIGN KEY (is_revision_of) REFERENCES tdocs(tdoc_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_wg ON tdocs(working_group)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_meeting_id ON tdocs(meeting_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_date_retrieved ON tdocs(date_retrieved)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_validated ON tdocs(validated)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tdocs_validation_failed ON tdocs(validation_failed)")

    # Crawl log table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crawl_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            working_groups TEXT NOT NULL,
            incremental INTEGER NOT NULL,
            items_added INTEGER DEFAULT 0,
            items_updated INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_log_crawl_type ON crawl_log(crawl_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_log_start_time ON crawl_log(start_time)")

    # Initialize reference data
    _populate_reference_tables(conn)

    conn.commit()


def _populate_reference_tables(conn: sqlite3.Connection) -> None:
    """Populate working_groups and subworking_groups tables from model definitions."""
    from tdoc_crawler.models import WorkingGroup

    # Working groups data
    working_groups_data = [(wg.tbid, wg.value, wg.value, wg.ftp_root) for wg in WorkingGroup]

    # Subworking groups data (from AGENTS.md specification)
    subworking_groups_data = [
        # SA groups
        (375, 375, "SP", "SA Plenary"),
        (384, 375, "S1", "SA1"),
        (385, 375, "S2", "SA2"),
        (386, 375, "S3", "SA3"),
        (387, 375, "S4", "SA4"),
        (388, 375, "S5", "SA5"),
        (825, 375, "S6", "SA6"),
        # CT groups
        (649, 649, "CP", "CT Plenary"),
        (651, 649, "C1", "CT1"),
        (652, 649, "C2", "CT2"),
        (653, 649, "C3", "CT3"),
        (654, 649, "C4", "CT4"),
        (655, 649, "C5", "CT5"),
        (656, 649, "C6", "CT6"),
        # RAN groups
        (373, 373, "RP", "RAN Plenary"),
        (379, 373, "R1", "RAN1"),
        (380, 373, "R2", "RAN2"),
        (381, 373, "R3", "RAN3"),
        (382, 373, "R4", "RAN4"),
        (657, 373, "R5", "RAN5"),
        (843, 373, "R6", "RAN6"),
    ]

    # Insert working groups
    conn.executemany(
        "INSERT OR IGNORE INTO working_groups (tbid, code, name, ftp_identifier) VALUES (?, ?, ?, ?)",
        working_groups_data,
    )

    # Insert subworking groups
    conn.executemany(
        "INSERT OR IGNORE INTO subworking_groups (subtb, tbid, code, name) VALUES (?, ?, ?, ?)",
        subworking_groups_data,
    )
