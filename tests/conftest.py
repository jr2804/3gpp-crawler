"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import TDocMetadata


@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory for tests.

    Args:
        tmp_path: Pytest's tmp_path fixture

    Returns:
        Path to test cache directory
    """
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
    """Get test database path.

    Args:
        test_cache_dir: Test cache directory

    Returns:
        Path to test database
    """
    return test_cache_dir / "tdoc_crawler.db"


@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
    """Create sample TDoc metadata for testing.

    Returns:
        List of sample TDocMetadata instances
    """
    return [
        TDocMetadata(
            tdoc_id="R1-2301234",
            url="https://www.3gpp.org/ftp/tsg_ran/RAN1/r1-2301234.zip",
            meeting_id=12345,
            file_size=256000,
            title="Sample RAN1 TDoc",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item="7.1",
            status="Approved",
            is_revision_of=None,
            document_type=None,
            checksum=None,
            source_path="RAN1/98/Docs/R1-2301234.zip",
            date_created=datetime(2023, 1, 15),
            date_retrieved=datetime(2023, 1, 16),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="R2-2301567",
            url="https://www.3gpp.org/ftp/tsg_ran/RAN2/r2-2301567.zip",
            meeting_id=12346,
            file_size=512000,
            title="Sample RAN2 TDoc",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item="8.1",
            status="Approved",
            is_revision_of=None,
            document_type=None,
            checksum=None,
            source_path="RAN2/98/Docs/R2-2301567.zip",
            date_created=datetime(2023, 1, 15),
            date_retrieved=datetime(2023, 1, 16),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="S4-2301890",
            url="https://www.3gpp.org/ftp/tsg_sa/SA4/s4-2301890.zip",
            meeting_id=12347,
            file_size=128000,
            title="Sample SA4 TDoc",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item="9.1",
            status="Approved",
            is_revision_of=None,
            document_type=None,
            checksum=None,
            source_path="SA4/134/Docs/S4-2301890.zip",
            date_created=datetime(2023, 1, 15),
            date_retrieved=datetime(2023, 1, 16),
            validated=False,
            validation_failed=False,
        ),
    ]


@pytest.fixture
def sample_meetings() -> list[dict]:
    """Create sample meeting metadata for testing.

    Returns:
        List of sample meeting dictionaries
    """
    return [
        {
            "meeting_id": 12345,
            "tbid": 373,  # RAN
            "subtb": 379,  # RAN1
            "short_name": "RAN1#98",
            "start_date": "2023-01-15",
            "end_date": "2023-01-19",
            "location": "Athens, Greece",
            "files_url": "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/RAN1_98/Docs/",
        },
        {
            "meeting_id": 12346,
            "tbid": 373,  # RAN
            "subtb": 380,  # RAN2
            "short_name": "RAN2#98",
            "start_date": "2023-01-15",
            "end_date": "2023-01-19",
            "location": "Athens, Greece",
            "files_url": "https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/RAN2_98/Docs/",
        },
        {
            "meeting_id": 12347,
            "tbid": 375,  # SA
            "subtb": 387,  # SA4
            "short_name": "SA4#134",
            "start_date": "2023-02-01",
            "end_date": "2023-02-05",
            "location": "Sophia Antipolis, France",
            "files_url": "https://www.3gpp.org/ftp/tsg_sa/WG4_Core/SA4_134/Docs/",
        },
    ]


@pytest.fixture
def populated_db(test_db_path: Path, sample_meetings: list[dict], sample_tdocs: list[TDocMetadata]) -> TDocDatabase:
    """Create and populate a test database.

    Args:
        test_db_path: Path to test database
        sample_meetings: Sample meeting metadata
        sample_tdocs: Sample TDoc metadata

    Returns:
        Populated TDocDatabase instance
    """
    with TDocDatabase(test_db_path) as db:
        insert_sample_meetings(db, sample_meetings)
        for tdoc in sample_tdocs:
            db.upsert_tdoc(tdoc)
    return TDocDatabase(test_db_path)


def insert_sample_meetings(database: TDocDatabase, meetings: list[dict]) -> None:
    """Insert sample meetings into database.

    Args:
        database: Database connection
        meetings: List of meeting dictionaries
    """
    from datetime import datetime

    for meeting in meetings:
        cursor = database.connection.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO meetings (
                meeting_id, tbid, subtb, short_name, start_date, end_date,
                location, files_url, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meeting["meeting_id"],
                meeting["tbid"],
                meeting["subtb"],
                meeting["short_name"],
                meeting["start_date"],
                meeting["end_date"],
                meeting["location"],
                meeting["files_url"],
                now,
                now,
            ),
        )
    database.connection.commit()


if __name__ == "__main__":
    pass
# end of file
