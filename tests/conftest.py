"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models import TDocMetadata, WorkingGroup


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
            working_group=WorkingGroup.RAN,
            subgroup="RAN1",
            meeting="RAN1#98",
            meeting_id=None,
            file_size=256000,
            title=None,
            contact=None,
            tdoc_type=None,
            for_purpose=None,
            agenda_item=None,
            status=None,
            is_revision_of=None,
            document_type=None,
            checksum=None,
            source_path=None,
            date_created=datetime(2023, 1, 15),
            date_retrieved=datetime(2023, 1, 16),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="R2-2301567",
            url="https://www.3gpp.org/ftp/tsg_ran/RAN2/r2-2301567.zip",
            working_group=WorkingGroup.RAN,
            subgroup="RAN2",
            meeting="RAN2#98",
            meeting_id=None,
            file_size=512000,
            title=None,
            contact=None,
            tdoc_type=None,
            for_purpose=None,
            agenda_item=None,
            status=None,
            is_revision_of=None,
            document_type=None,
            checksum=None,
            source_path=None,
            date_created=datetime(2023, 1, 15),
            date_retrieved=datetime(2023, 1, 16),
            validated=False,
            validation_failed=False,
        ),
        TDocMetadata(
            tdoc_id="S4-2301890",
            url="https://www.3gpp.org/ftp/tsg_sa/SA4/s4-2301890.zip",
            working_group=WorkingGroup.SA,
            subgroup="SA4",
            meeting="SA4#134",
            meeting_id=None,
            file_size=128000,
            title=None,
            contact=None,
            tdoc_type=None,
            for_purpose=None,
            agenda_item=None,
            status=None,
            is_revision_of=None,
            document_type=None,
            checksum=None,
            source_path=None,
            date_created=datetime(2023, 1, 15),
            date_retrieved=datetime(2023, 1, 16),
            validated=False,
            validation_failed=False,
        ),
    ]


@pytest.fixture
def populated_db(test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> TDocDatabase:
    """Create and populate a test database.

    Args:
        test_db_path: Path to test database
        sample_tdocs: Sample TDoc metadata

    Returns:
        Populated TDocDatabase instance
    """
    with TDocDatabase(test_db_path) as db:
        for tdoc in sample_tdocs:
            db.upsert_tdoc(tdoc)
    return TDocDatabase(test_db_path)


if __name__ == "__main__":
    pass
# end of file
