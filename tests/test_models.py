"""Tests for models module."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from tdoc_crawler.models import WorkingGroup
from tdoc_crawler.models.subworking_groups import SubWorkingGroup
from tdoc_crawler.tdocs.models import TDocCrawlConfig, TDocMetadata, TDocQueryConfig


class TestTDocMetadata:
    """Tests for TDocMetadata model."""

    def test_creation(self) -> None:
        """Test creating TDocMetadata instance."""
        metadata = TDocMetadata(
            tdoc_id="R1-2301234",
            meeting_id=0,
            title="Test TDoc",
            url="https://www.3gpp.org/test.zip",
            source="Test Source",
            contact="Test Contact",
            agenda_item_nbr=Decimal("7.1"),
        )
        assert metadata.tdoc_id == "R1-2301234"
        assert metadata.url == "https://www.3gpp.org/test.zip"
        assert metadata.title == "Test TDoc"

    def test_case_normalization(self) -> None:
        """Test TDoc ID case normalization to uppercase."""
        metadata = TDocMetadata(
            tdoc_id="r1-2301234",
            meeting_id=0,
            title="Test TDoc",
            url="https://www.3gpp.org/test.zip",
            source="Test Source",
            contact="Test Contact",
            agenda_item_nbr=Decimal("7.1"),
        )
        assert metadata.tdoc_id == "R1-2301234"

    def test_optional_fields(self) -> None:
        """Test optional fields in TDocMetadata."""
        metadata = TDocMetadata(
            tdoc_id="S4-2301890",
            meeting_id=12345,
            title="Test TDoc",
            url="https://www.3gpp.org/test.zip",
            source="Test Source",
            contact="Test Contact",
            agenda_item_nbr=Decimal("7.1"),
            file_size=256000,
        )
        assert metadata.meeting_id == 12345
        assert metadata.file_size == 256000


class TestTDocCrawlConfig:
    """Tests for TDocCrawlConfig model."""

    def test_default_config(self) -> None:
        """Test TDocCrawlConfig with defaults."""
        config = TDocCrawlConfig(
            incremental=True,
            timeout=30,
        )
        assert config.incremental is True
        assert config.timeout == 30
        assert len(config.working_groups) == 3

    def test_custom_config(self) -> None:
        """Test TDocCrawlConfig with custom values."""
        config = TDocCrawlConfig(
            working_groups=[WorkingGroup.RAN],
            incremental=False,
            timeout=60,
        )
        assert config.incremental is False
        assert config.timeout == 60
        assert len(config.working_groups) == 1


class TestTDocQueryConfig:
    """Tests for TDocQueryConfig model."""

    def test_default_query_config(self) -> None:
        """Test TDocQueryConfig with defaults."""
        config = TDocQueryConfig(output_format="table")
        assert config.output_format.value == "table"
        assert config.tdoc_ids is None
        assert config.working_groups is None
        assert config.limit is None

    def test_query_with_tdoc_ids(self) -> None:
        """Test TDocQueryConfig with TDoc IDs."""
        config = TDocQueryConfig(
            output_format="table",
            tdoc_ids=["r1-2301234", "S4-2301890"],
        )
        tdoc_ids = config.tdoc_ids
        assert tdoc_ids is not None
        assert len(tdoc_ids) == 2
        assert tdoc_ids[0] == "R1-2301234"
        assert tdoc_ids[1] == "S4-2301890"

    def test_query_with_filters(self) -> None:
        """Test TDocQueryConfig with multiple filters."""
        start = datetime(2023, 1, 1)
        end = datetime(2023, 1, 31)
        config = TDocQueryConfig(
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
        assert config.output_format.value == "json"


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

    def test_working_group_literal(self) -> None:
        """Test WorkingGroup literal property returns single character."""
        assert WorkingGroup.RAN.literal == "R"
        assert WorkingGroup.SA.literal == "S"
        assert WorkingGroup.CT.literal == "C"

    def test_working_group_tbid(self) -> None:
        """Test WorkingGroup technical body ID mapping."""
        assert WorkingGroup.RAN.tbid == 373
        assert WorkingGroup.SA.tbid == 375
        assert WorkingGroup.CT.tbid == 649

    def test_working_group_from_literal(self) -> None:
        """Test parsing working group from single character."""
        assert WorkingGroup.from_literal("RAN") == WorkingGroup.RAN
        assert WorkingGroup.from_literal("r") == WorkingGroup.RAN
        assert WorkingGroup.from_literal("SA") == WorkingGroup.SA
        assert WorkingGroup.from_literal("s") == WorkingGroup.SA
        assert WorkingGroup.from_literal("CT") == WorkingGroup.CT
        assert WorkingGroup.from_literal("c") == WorkingGroup.CT

    def test_working_group_from_literal_with_spaces(self) -> None:
        """Test parsing working group with surrounding whitespace."""
        assert WorkingGroup.from_literal("  r  ") == WorkingGroup.RAN
        assert WorkingGroup.from_literal("  S  ") == WorkingGroup.SA
        assert WorkingGroup.from_literal("  C  ") == WorkingGroup.CT

    def test_working_group_from_literal_invalid(self) -> None:
        """Test that invalid literal raises ValueError."""
        with pytest.raises(ValueError, match="Unknown working group literal"):
            WorkingGroup.from_literal("X")


class TestSubWorkingGroup:
    """Tests for SubWorkingGroup enum."""

    def test_subworking_group_values(self) -> None:
        """Test SubWorkingGroup enum values."""
        # SA subgroups
        assert SubWorkingGroup.SP.value == "SA Plenary"
        assert SubWorkingGroup.S1.value == "SA1"
        assert SubWorkingGroup.S2.value == "SA2"
        assert SubWorkingGroup.S3.value == "SA3"
        assert SubWorkingGroup.S4.value == "SA4"
        assert SubWorkingGroup.S5.value == "SA5"
        assert SubWorkingGroup.S6.value == "SA6"
        # CT subgroups
        assert SubWorkingGroup.CP.value == "CT Plenary"
        assert SubWorkingGroup.C1.value == "CT1"
        assert SubWorkingGroup.C2.value == "CT2"
        assert SubWorkingGroup.C3.value == "CT3"
        assert SubWorkingGroup.C4.value == "CT4"
        assert SubWorkingGroup.C5.value == "CT5"
        assert SubWorkingGroup.C6.value == "CT6"
        # RAN subgroups
        assert SubWorkingGroup.RP.value == "RAN Plenary"
        assert SubWorkingGroup.R1.value == "RAN1"
        assert SubWorkingGroup.R2.value == "RAN2"
        assert SubWorkingGroup.R3.value == "RAN3"
        assert SubWorkingGroup.R4.value == "RAN4"
        assert SubWorkingGroup.R5.value == "RAN5"
        assert SubWorkingGroup.R6.value == "RAN6"

    def test_subworking_group_creation(self) -> None:
        """Test creating SubWorkingGroup from strings."""
        s4 = SubWorkingGroup("SA4")
        assert s4 == SubWorkingGroup.S4
        r1 = SubWorkingGroup("RAN1")
        assert r1 == SubWorkingGroup.R1
        c3 = SubWorkingGroup("CT3")
        assert c3 == SubWorkingGroup.C3

    def test_subworking_group_subtb(self) -> None:
        """Test SubWorkingGroup technical body ID mapping."""
        # SA subgroups
        assert SubWorkingGroup.SP.subtb == 375
        assert SubWorkingGroup.S1.subtb == 384
        assert SubWorkingGroup.S2.subtb == 385
        assert SubWorkingGroup.S3.subtb == 386
        assert SubWorkingGroup.S4.subtb == 387
        assert SubWorkingGroup.S5.subtb == 388
        assert SubWorkingGroup.S6.subtb == 825
        # CT subgroups
        assert SubWorkingGroup.CP.subtb == 649
        assert SubWorkingGroup.C1.subtb == 651
        assert SubWorkingGroup.C2.subtb == 652
        assert SubWorkingGroup.C3.subtb == 653
        assert SubWorkingGroup.C4.subtb == 654
        assert SubWorkingGroup.C5.subtb == 655
        assert SubWorkingGroup.C6.subtb == 656
        # RAN subgroups
        assert SubWorkingGroup.RP.subtb == 373
        assert SubWorkingGroup.R1.subtb == 379
        assert SubWorkingGroup.R2.subtb == 380
        assert SubWorkingGroup.R3.subtb == 381
        assert SubWorkingGroup.R4.subtb == 382
        assert SubWorkingGroup.R5.subtb == 657
        assert SubWorkingGroup.R6.subtb == 843

    def test_subworking_group_from_wg_and_nbr(self) -> None:
        """Test constructing SubWorkingGroup from working group and number."""
        # SA subgroups
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.SA, "1") == SubWorkingGroup.S1
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.SA, "2") == SubWorkingGroup.S2
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.SA, "4") == SubWorkingGroup.S4
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.SA, "P") == SubWorkingGroup.SP
        # CT subgroups
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.CT, "1") == SubWorkingGroup.C1
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.CT, "3") == SubWorkingGroup.C3
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.CT, "P") == SubWorkingGroup.CP
        # RAN subgroups
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.RAN, "1") == SubWorkingGroup.R1
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.RAN, "2") == SubWorkingGroup.R2
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.RAN, "P") == SubWorkingGroup.RP

    def test_subworking_group_from_wg_and_nbr_integer(self) -> None:
        """Test constructing SubWorkingGroup with integer input."""
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.SA, 4) == SubWorkingGroup.S4
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.RAN, 2) == SubWorkingGroup.R2
        assert SubWorkingGroup.from_wg_and_nbr(WorkingGroup.CT, 5) == SubWorkingGroup.C5

    def test_subworking_group_from_wg_and_nbr_invalid(self) -> None:
        """Test that invalid subgroup code raises ValueError."""
        with pytest.raises(ValueError, match="Unknown subgroup code"):
            SubWorkingGroup.from_wg_and_nbr(WorkingGroup.RAN, "7")


class TestNormalizeWorkingGroupAlias:
    """Tests for normalize_working_group_alias function."""

    def test_normalize_ran_variants(self) -> None:
        """Test RAN working group alias normalization."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        assert normalize_working_group_alias("RAN") == WorkingGroup.RAN
        assert normalize_working_group_alias("ran") == WorkingGroup.RAN
        assert normalize_working_group_alias("R") == WorkingGroup.RAN
        assert normalize_working_group_alias("r") == WorkingGroup.RAN

    def test_normalize_sa_variants(self) -> None:
        """Test SA working group alias normalization."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        assert normalize_working_group_alias("SA") == WorkingGroup.SA
        assert normalize_working_group_alias("sa") == WorkingGroup.SA
        assert normalize_working_group_alias("S") == WorkingGroup.SA
        assert normalize_working_group_alias("s") == WorkingGroup.SA

    def test_normalize_ct_variants(self) -> None:
        """Test CT working group alias normalization."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        assert normalize_working_group_alias("CT") == WorkingGroup.CT
        assert normalize_working_group_alias("ct") == WorkingGroup.CT
        assert normalize_working_group_alias("C") == WorkingGroup.CT
        assert normalize_working_group_alias("c") == WorkingGroup.CT

    def test_normalize_with_hyphen(self) -> None:
        """Test working group normalization with hyphens."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        assert normalize_working_group_alias("RAN-") == WorkingGroup.RAN
        assert normalize_working_group_alias("SA-") == WorkingGroup.SA
        assert normalize_working_group_alias("CT-") == WorkingGroup.CT

    def test_normalize_with_space(self) -> None:
        """Test working group normalization with spaces."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        assert normalize_working_group_alias("RAN ") == WorkingGroup.RAN
        assert normalize_working_group_alias(" SA ") == WorkingGroup.SA
        assert normalize_working_group_alias(" CT") == WorkingGroup.CT

    def test_normalize_with_hash(self) -> None:
        """Test working group normalization with hash symbol."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        assert normalize_working_group_alias("RAN#") == WorkingGroup.RAN
        assert normalize_working_group_alias("SA#") == WorkingGroup.SA
        assert normalize_working_group_alias("CT#") == WorkingGroup.CT

    def test_normalize_invalid_alias(self) -> None:
        """Test that invalid alias raises ValueError."""
        from tdoc_crawler.meetings.utils import normalize_working_group_alias

        with pytest.raises(ValueError, match="Unknown working group"):
            normalize_working_group_alias("XYZ")


class TestNormalizeSubgroupAlias:
    """Tests for normalize_subgroup_alias function."""

    def test_normalize_short_codes(self) -> None:
        """Test normalizing short subgroup codes."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("S4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("R1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("C3") == SubWorkingGroup.C3
        assert normalize_subgroup_alias("RP") == SubWorkingGroup.RP
        assert normalize_subgroup_alias("SP") == SubWorkingGroup.SP
        assert normalize_subgroup_alias("CP") == SubWorkingGroup.CP

    def test_normalize_full_names(self) -> None:
        """Test normalizing full subgroup names."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("SA4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("RAN1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("CT3") == SubWorkingGroup.C3

    def test_normalize_separators_hyphen(self) -> None:
        """Test normalizing with hyphen separators."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("SA-4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("RAN-1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("CT-3") == SubWorkingGroup.C3

    def test_normalize_separators_hash(self) -> None:
        """Test normalizing with hash separators."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("SA#4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("RAN#1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("CT#3") == SubWorkingGroup.C3

    def test_normalize_separators_space(self) -> None:
        """Test normalizing with space separators."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("SA 4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("RAN 1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("CT 3") == SubWorkingGroup.C3

    def test_normalize_plenary_variants(self) -> None:
        """Test normalizing plenary subgroup variants."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("RP") == SubWorkingGroup.RP
        assert normalize_subgroup_alias("RAN PLENARY") == SubWorkingGroup.RP
        assert normalize_subgroup_alias("SP") == SubWorkingGroup.SP
        assert normalize_subgroup_alias("SA PLENARY") == SubWorkingGroup.SP
        assert normalize_subgroup_alias("CP") == SubWorkingGroup.CP
        assert normalize_subgroup_alias("CT PLENARY") == SubWorkingGroup.CP

    def test_normalize_all_sa_subgroups(self) -> None:
        """Test normalizing all SA subgroups."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("S1") == SubWorkingGroup.S1
        assert normalize_subgroup_alias("S2") == SubWorkingGroup.S2
        assert normalize_subgroup_alias("S3") == SubWorkingGroup.S3
        assert normalize_subgroup_alias("S4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("S5") == SubWorkingGroup.S5
        assert normalize_subgroup_alias("S6") == SubWorkingGroup.S6

    def test_normalize_all_ct_subgroups(self) -> None:
        """Test normalizing all CT subgroups."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("C1") == SubWorkingGroup.C1
        assert normalize_subgroup_alias("C2") == SubWorkingGroup.C2
        assert normalize_subgroup_alias("C3") == SubWorkingGroup.C3
        assert normalize_subgroup_alias("C4") == SubWorkingGroup.C4
        assert normalize_subgroup_alias("C5") == SubWorkingGroup.C5
        assert normalize_subgroup_alias("C6") == SubWorkingGroup.C6

    def test_normalize_all_ran_subgroups(self) -> None:
        """Test normalizing all RAN subgroups."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        assert normalize_subgroup_alias("R1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("R2") == SubWorkingGroup.R2
        assert normalize_subgroup_alias("R3") == SubWorkingGroup.R3
        assert normalize_subgroup_alias("R4") == SubWorkingGroup.R4
        assert normalize_subgroup_alias("R5") == SubWorkingGroup.R5
        assert normalize_subgroup_alias("R6") == SubWorkingGroup.R6

    def test_normalize_invalid_subgroup(self) -> None:
        """Test that invalid subgroup raises ValueError."""
        from tdoc_crawler.meetings.utils import normalize_subgroup_alias

        with pytest.raises(ValueError, match="Unknown working group"):
            normalize_subgroup_alias("XYZ")
