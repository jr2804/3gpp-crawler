"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tdoc_crawler.config import CacheManager
from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.database import MeetingDatabase, TDocDatabase
from tdoc_crawler.database.oxyde_models import TDocMetadata
from tdoc_crawler.meetings.models import MeetingMetadata


@pytest.fixture(autouse=True)
def _reset_cache_manager() -> None:
    """Reset CacheManager singleton before each test.

    The CLI callback registers a CacheManager singleton on every invocation.
    Without resetting between tests, the second test that invokes the CLI
    will fail with "CacheManager already registered".
    """
    CacheManager._instance = None


@pytest.fixture
def test_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary cache directory for tests.

    Also sets TDC_CACHE_DIR env var so CLI tests pick up the temp directory.

    Args:
        tmp_path: Pytest's tmp_path fixture
        monkeypatch: Pytest's monkeypatch fixture

    Returns:
        Path to test cache directory
    """
    cache_dir = tmp_path / "test-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TDC_CACHE_DIR", str(cache_dir))
    return cache_dir


@pytest.fixture
def test_db_path(test_cache_dir: Path) -> Path:
    """Get test database path.

    Args:
        test_cache_dir: Test cache directory

    Returns:
        Path to test database
    """
    return PathConfig(cache_dir=test_cache_dir).db_file


@pytest.fixture
def sample_tdocs() -> list[TDocMetadata]:
    """Create sample TDoc metadata for testing.

    Returns:
        List of sample TDocMetadata instances
    """
    return [
        TDocMetadata(
            tdoc_id="R1-2301234",
            tbid=373,
            url="https://www.3gpp.org/ftp/tsg_ran/RAN1/r1-2301234.zip",
            meeting_id=12345,
            file_size=256000,
            title="Sample RAN1 TDoc",
            source="Test Source",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr="7.1",
            agenda_item_text="Test agenda item",
            status="approved",
            is_revision_of="",
            date_created=datetime(2023, 1, 15, tzinfo=UTC),
            date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="R2-2301567",
            tbid=373,
            url="https://www.3gpp.org/ftp/tsg_ran/RAN2/r2-2301567.zip",
            meeting_id=12346,
            file_size=512000,
            title="Sample RAN2 TDoc",
            source="Test Source",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr="8.1",
            agenda_item_text="Test agenda item",
            status="approved",
            is_revision_of="",
            date_created=datetime(2023, 1, 15, tzinfo=UTC),
            date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="S4-2301890",
            tbid=375,
            url="https://www.3gpp.org/ftp/tsg_sa/SA4/s4-2301890.zip",
            meeting_id=12347,
            file_size=128000,
            title="Sample SA4 TDoc",
            source="Test Source",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr="9.1",
            agenda_item_text="Test agenda item",
            status="approved",
            is_revision_of="",
            date_created=datetime(2023, 1, 15, tzinfo=UTC),
            date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
            validated=False,
            validation_failed=False,
        ),
    ]


@pytest.fixture
def sample_meetings() -> list[dict[str, object]]:
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
def populated_db(
    test_db_path: Path,
    sample_meetings: list[dict[str, object]],
    sample_tdocs: list[TDocMetadata],
) -> TDocDatabase:
    """Create and populate a test database.

    Args:
        test_db_path: Path to test database
        sample_meetings: Sample meeting metadata
        sample_tdocs: Sample TDoc metadata

    Returns:
        Populated TDocDatabase instance
    """

    async def _populate() -> None:
        async with TDocDatabase(test_db_path) as db:
            await insert_sample_meetings_async(db, sample_meetings)
            for tdoc in sample_tdocs:
                _ = await db.upsert_tdoc(tdoc)

    asyncio.run(_populate())
    return TDocDatabase(test_db_path)


async def insert_sample_meetings_async(database: MeetingDatabase, meetings: list[dict[str, object]]) -> None:
    """Insert sample meetings into database using the proper database API.

    This function uses db.upsert_meeting() instead of raw SQL to ensure
    consistency with the MeetingMetadata model and database layer validation.

    Args:
        database: Database connection
        meetings: List of meeting dictionaries with keys:
            - meeting_id: Integer meeting ID
            - tbid: Technical body ID (working group)
            - subtb: Sub-technical body ID (subworking group)
            - short_name: Short meeting name (e.g., "RAN1#98")
            - start_date: Start date as ISO string (YYYY-MM-DD)
            - end_date: End date as ISO string (YYYY-MM-DD)
            - location: Meeting location
            - files_url: URL to meeting files
    """
    for meeting_dict in meetings:
        meeting_id = int(str(meeting_dict.get("meeting_id", 0)))
        tbid = int(str(meeting_dict.get("tbid", 0)))
        subtb_raw = meeting_dict.get("subtb")
        subtb = int(str(subtb_raw)) if subtb_raw is not None else None
        short_name = str(meeting_dict.get("short_name", ""))
        location_raw = meeting_dict.get("location")
        location = str(location_raw) if location_raw else None
        files_url_raw = meeting_dict.get("files_url")
        files_url = str(files_url_raw) if files_url_raw else None
        # Parse date strings to date objects
        start_date_str = meeting_dict.get("start_date")
        end_date_str = meeting_dict.get("end_date")

        start_date = date.fromisoformat(str(start_date_str)) if start_date_str else None
        end_date = date.fromisoformat(str(end_date_str)) if end_date_str else None

        # Create MeetingMetadata using the database API
        meeting_metadata = MeetingMetadata(
            meeting_id=meeting_id,
            tbid=tbid,
            subtb=subtb,
            short_name=short_name,
            title=None,
            start_date=start_date,
            end_date=end_date,
            location=location,
            files_url=files_url,
            portal_url=None,
            tdoc_count=0,
        )

        # Use the proper database API instead of raw SQL
        _ = await database.upsert_meeting(meeting_metadata)


def insert_sample_meetings(database: MeetingDatabase, meetings: list[dict[str, object]]) -> None:
    """Synchronous compatibility wrapper around async meeting insertion helper."""
    asyncio.run(insert_sample_meetings_async(database, meetings))


if __name__ == "__main__":
    pass
# end of file
