"""Tests for models module."""

from __future__ import annotations

from datetime import datetime

from tdoc_crawler.models import CrawlConfig, QueryConfig, TDocMetadata, WorkingGroup


class TestTDocMetadata:
    """Tests for TDocMetadata model."""

    def test_creation(self) -> None:
        """Test creating TDocMetadata instance."""
        metadata = TDocMetadata(
            tdoc_id="R1-2301234",
            url="ftp://ftp.3gpp.org/test.zip",
            working_group=WorkingGroup.RAN,
        )
        assert metadata.tdoc_id == "R1-2301234"
        assert metadata.working_group == WorkingGroup.RAN

    def test_case_normalization(self) -> None:
        """Test TDoc ID case normalization to uppercase."""
        metadata = TDocMetadata(
            tdoc_id="r1-2301234",
            url="ftp://ftp.3gpp.org/test.zip",
            working_group=WorkingGroup.RAN,
        )
        assert metadata.tdoc_id == "R1-2301234"

    def test_optional_fields(self) -> None:
        """Test optional fields in TDocMetadata."""
        metadata = TDocMetadata(
            tdoc_id="S4-2301890",
            url="ftp://ftp.3gpp.org/test.zip",
            working_group=WorkingGroup.SA,
            subgroup="SA4",
            meeting="SA4#134",
            file_size=256000,
        )
        assert metadata.subgroup == "SA4"
        assert metadata.meeting == "SA4#134"
        assert metadata.file_size == 256000


class TestCrawlConfig:
    """Tests for CrawlConfig model."""

    def test_default_config(self) -> None:
        """Test CrawlConfig with defaults."""
        config = CrawlConfig(
            incremental=True,
            max_retries=3,
            timeout=30,
            verbose=False,
        )
        assert config.incremental is True
        assert config.max_retries == 3
        assert config.timeout == 30
        assert len(config.working_groups) == 3

    def test_custom_config(self) -> None:
        """Test CrawlConfig with custom values."""
        config = CrawlConfig(
            working_groups=[WorkingGroup.RAN],
            incremental=False,
            max_retries=5,
            timeout=60,
            verbose=True,
        )
        assert config.incremental is False
        assert config.max_retries == 5
        assert config.timeout == 60
        assert config.verbose is True
        assert len(config.working_groups) == 1


class TestQueryConfig:
    """Tests for QueryConfig model."""

    def test_default_query_config(self) -> None:
        """Test QueryConfig with defaults."""
        config = QueryConfig(output_format="table")
        assert config.output_format == "table"
        assert config.tdoc_ids is None
        assert config.working_groups is None
        assert config.limit is None

    def test_query_with_tdoc_ids(self) -> None:
        """Test QueryConfig with TDoc IDs."""
        config = QueryConfig(
            output_format="table",
            tdoc_ids=["r1-2301234", "S4-2301890"],
        )
        tdoc_ids = config.tdoc_ids
        assert tdoc_ids is not None
        assert len(tdoc_ids) == 2
        assert tdoc_ids[0] == "R1-2301234"
        assert tdoc_ids[1] == "S4-2301890"

    def test_query_with_filters(self) -> None:
        """Test QueryConfig with multiple filters."""
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)
        config = QueryConfig(
            output_format="json",
            working_groups=[WorkingGroup.RAN, WorkingGroup.SA],
            start_date=start,
            end_date=end,
            limit=100,
        )
        working_groups = config.working_groups
        assert working_groups is not None
        assert len(working_groups) == 2
        assert config.start_date == start
        assert config.end_date == end
        assert config.limit == 100
        assert config.output_format == "json"


class TestWorkingGroup:
    """Tests for WorkingGroup enum."""

    def test_working_group_values(self) -> None:
        """Test WorkingGroup enum values."""
        assert WorkingGroup.RAN.value == "RAN"
        assert WorkingGroup.SA.value == "SA"
        assert WorkingGroup.CT.value == "CT"

    def test_working_group_creation(self) -> None:
        """Test creating WorkingGroup from strings."""
        ran = WorkingGroup("RAN")
        assert ran == WorkingGroup.RAN
        sa = WorkingGroup("SA")
        assert sa == WorkingGroup.SA
        ct = WorkingGroup("CT")
        assert ct == WorkingGroup.CT
