"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tdoc_crawler.config import CacheManager, register_cache_manager
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import MeetingMetadata, TDocMetadata, WorkingGroup


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

    # Register cache manager for tests (use force=True to allow re-registration)
    cache_manager = CacheManager(cache_dir, name="default", ensure_paths=True)
    register_cache_manager(cache_manager, force=True)

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
            source="Test Source",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("7.1"),
            agenda_item_text="Test agenda item",
            status="Approved",
            is_revision_of=None,
            date_created=datetime(2023, 1, 15, tzinfo=UTC),
            date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="R2-2301567",
            url="https://www.3gpp.org/ftp/tsg_ran/RAN2/r2-2301567.zip",
            meeting_id=12346,
            file_size=512000,
            title="Sample RAN2 TDoc",
            source="Test Source",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("8.1"),
            agenda_item_text="Test agenda item",
            status="Approved",
            is_revision_of=None,
            date_created=datetime(2023, 1, 15, tzinfo=UTC),
            date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="S4-2301890",
            url="https://www.3gpp.org/ftp/tsg_sa/SA4/s4-2301890.zip",
            meeting_id=12347,
            file_size=128000,
            title="Sample SA4 TDoc",
            source="Test Source",
            contact="Test Contact",
            tdoc_type="Discussion",
            for_purpose="Discussion",
            agenda_item_nbr=Decimal("9.1"),
            agenda_item_text="Test agenda item",
            status="Approved",
            is_revision_of=None,
            date_created=datetime(2023, 1, 15, tzinfo=UTC),
            date_retrieved=datetime(2023, 1, 16, tzinfo=UTC),
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
    # Map tbid to WorkingGroup enum
    tbid_to_wg = {
        373: WorkingGroup.RAN,  # RAN
        375: WorkingGroup.SA,  # SA
        649: WorkingGroup.CT,  # CT
    }

    # Map subtb to subgroup name
    subtb_to_sg = {
        373: "RP",  # RAN Plenary
        379: "R1",  # RAN1
        380: "R2",  # RAN2
        381: "R3",  # RAN3
        382: "R4",  # RAN4
        657: "R5",  # RAN5
        843: "R6",  # RAN6
        375: "SP",  # SA Plenary
        384: "S1",  # SA1
        385: "S2",  # SA2
        386: "S3",  # SA3
        387: "S4",  # SA4
        388: "S5",  # SA5
        825: "S6",  # SA6
        649: "CP",  # CT Plenary
        651: "C1",  # CT1
        652: "C2",  # CT2
        653: "C3",  # CT3
        654: "C4",  # CT4
        655: "C5",  # CT5
        656: "C6",  # CT6
    }

    for meeting_dict in meetings:
        # Parse date strings to date objects
        start_date_str = meeting_dict.get("start_date")
        end_date_str = meeting_dict.get("end_date")

        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str) if end_date_str else None

        # Create MeetingMetadata using the database API
        tbid = meeting_dict["tbid"]
        subtb = meeting_dict["subtb"]

        meeting_metadata = MeetingMetadata(
            meeting_id=meeting_dict["meeting_id"],
            tbid=tbid,
            subtb=subtb,
            working_group=tbid_to_wg.get(tbid, WorkingGroup.RAN),
            subgroup=subtb_to_sg.get(subtb),
            short_name=meeting_dict["short_name"],
            title=None,
            start_date=start_date,
            end_date=end_date,
            location=meeting_dict.get("location"),
            files_url=meeting_dict.get("files_url"),
            portal_url=None,
        )

        # Use the proper database API instead of raw SQL
        database.upsert_meeting(meeting_metadata)


if __name__ == "__main__":
    pass
# end of file
