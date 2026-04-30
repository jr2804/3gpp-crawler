"""Unit tests for normalization functions."""

from __future__ import annotations

import pytest

from tdoc_crawler.models.subworking_groups import SubWorkingGroup
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.utils.normalization import (
    NormalizationError,
    expand_spec_ranges,
    expand_spec_ranges_batch,
    normalize_portal_meeting_name,
    normalize_release,
    normalize_release_version,
    normalize_spec_number,
    normalize_subgroup_alias,
    normalize_tdoc_id,
    normalize_tdoc_ids,
    normalize_working_group_alias,
)


class TestNormalizeTdocId:
    """Tests for normalize_tdoc_id."""

    def test_lowercase_to_uppercase(self) -> None:
        result = normalize_tdoc_id("s4-250638")
        assert result == "S4-250638"

    def test_whitespace_stripped(self) -> None:
        result = normalize_tdoc_id("  S4-250638  ")
        assert result == "S4-250638"

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="TDoc ID cannot be empty"):
            normalize_tdoc_id("")

    def test_mixed_case(self) -> None:
        result = normalize_tdoc_id("RaN1-123")
        assert result == "RAN1-123"


class TestNormalizeTdocIds:
    """Tests for normalize_tdoc_ids."""

    def test_multiple_ids_normalized(self) -> None:
        result = normalize_tdoc_ids(["s4-250638", "RAN1-123"])
        assert result == ["S4-250638", "RAN1-123"]

    def test_none_input(self) -> None:
        result = normalize_tdoc_ids(None)
        assert result is None

    def test_empty_list(self) -> None:
        result = normalize_tdoc_ids([])
        assert result == []


class TestNormalizeSpecNumber:
    """Tests for normalize_spec_number."""

    def test_already_dotted(self) -> None:
        result = normalize_spec_number("26.132")
        assert result == "26.132"

    def test_undotted_to_dotted(self) -> None:
        result = normalize_spec_number("26260")
        assert result == "26.260"

    def test_with_3gpp_prefix(self) -> None:
        result = normalize_spec_number("3GPP TS 26.132")
        assert result == "26.132"

    def test_with_tr_prefix(self) -> None:
        result = normalize_spec_number("TR 26260")
        assert result == "26.260"

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(NormalizationError):
            normalize_spec_number("invalid")

    def test_series_only_raises(self) -> None:
        with pytest.raises(NormalizationError):
            normalize_spec_number("26")


class TestNormalizeRelease:
    """Tests for normalize_release."""

    def test_latest(self) -> None:
        result = normalize_release("latest")
        assert result == ("latest", None, None)

    def test_all(self) -> None:
        result = normalize_release("all")
        assert result == ("all", None, None)

    def test_full_version(self) -> None:
        result = normalize_release("18.0.0")
        assert result == ("exact", "18.0.0", 3)

    def test_partial_major_minor(self) -> None:
        result = normalize_release("18.1")
        assert result == ("prefix", "18.1", 2)

    def test_partial_major_only(self) -> None:
        result = normalize_release("18")
        assert result == ("prefix", "18", 1)

    def test_v_prefix(self) -> None:
        result = normalize_release("v18")
        assert result == ("prefix", "18", 1)

    def test_rel_prefix(self) -> None:
        result = normalize_release("Rel-18")
        assert result == ("prefix", "-18", 1)

    def test_rel_prefix_lowercase(self) -> None:
        result = normalize_release("rel18")
        assert result == ("prefix", "18", 1)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_release("invalid")


class TestNormalizePortalMeetingName:
    """Tests for normalize_portal_meeting_name."""

    def test_sa4_format(self) -> None:
        result = normalize_portal_meeting_name("SA4#133-e")
        assert result == "S4-133-e"

    def test_ran1_format(self) -> None:
        result = normalize_portal_meeting_name("RAN1#123")
        assert result == "R1-123"

    def test_empty_string(self) -> None:
        result = normalize_portal_meeting_name("")
        assert result == ""

    def test_none_input(self) -> None:
        result = normalize_portal_meeting_name(None)
        assert result == ""


class TestNormalizeReleaseVersion:
    """Tests for normalize_release_version."""

    def test_major_only(self) -> None:
        result = normalize_release_version("19")
        assert result == "19.0.0"

    def test_major_minor(self) -> None:
        result = normalize_release_version("19.1")
        assert result == "19.1.0"

    def test_rel_prefix(self) -> None:
        result = normalize_release_version("rel-19")
        assert result == "19.0.0"

    def test_full_version(self) -> None:
        result = normalize_release_version("19.1.2")
        assert result == "19.1.2"


class TestNormalizeWorkingGroupAlias:
    """Tests for normalize_working_group_alias."""

    def test_sa_variants(self) -> None:
        assert normalize_working_group_alias("SA") == WorkingGroup.SA
        assert normalize_working_group_alias("S4") == WorkingGroup.SA
        assert normalize_working_group_alias("SA4") == WorkingGroup.SA

    def test_ran_variants(self) -> None:
        assert normalize_working_group_alias("RAN") == WorkingGroup.RAN
        assert normalize_working_group_alias("R1") == WorkingGroup.RAN
        assert normalize_working_group_alias("RAN1") == WorkingGroup.RAN

    def test_ct_variants(self) -> None:
        assert normalize_working_group_alias("CT") == WorkingGroup.CT
        assert normalize_working_group_alias("C3") == WorkingGroup.CT
        assert normalize_working_group_alias("CT3") == WorkingGroup.CT

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_working_group_alias("UNKNOWN")


class TestNormalizeSubgroupAlias:
    """Tests for normalize_subgroup_alias."""

    def test_s4_variants(self) -> None:
        assert normalize_subgroup_alias("S4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("SA4") == SubWorkingGroup.S4
        assert normalize_subgroup_alias("SA-4") == SubWorkingGroup.S4

    def test_r1_variants(self) -> None:
        assert normalize_subgroup_alias("R1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("RAN1") == SubWorkingGroup.R1
        assert normalize_subgroup_alias("RAN-1") == SubWorkingGroup.R1

    def test_ct3_variants(self) -> None:
        assert normalize_subgroup_alias("C3") == SubWorkingGroup.C3
        assert normalize_subgroup_alias("CT3") == SubWorkingGroup.C3
        assert normalize_subgroup_alias("CT-3") == SubWorkingGroup.C3

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            normalize_subgroup_alias("UNKNOWN")


class TestExpandSpecRanges:
    """Tests for expand_spec_ranges."""

    def test_dotted_range(self) -> None:
        result = list(expand_spec_ranges("26.260-26.266"))
        assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    def test_colon_range(self) -> None:
        result = list(expand_spec_ranges("26.260:26.262"))
        assert result == ["26.260", "26.261", "26.262"]

    def test_offset_syntax(self) -> None:
        result = list(expand_spec_ranges("26.260+6"))
        assert result == ["26.260", "26.261", "26.262", "26.263", "26.264", "26.265", "26.266"]

    def test_single_spec(self) -> None:
        result = list(expand_spec_ranges("26.260"))
        assert result == ["26.260"]


class TestExpandSpecRangesBatch:
    """Tests for expand_spec_ranges_batch."""

    def test_mixed_valid_invalid(self) -> None:
        result = expand_spec_ranges_batch(["26.260-26.262", "invalid", "26.270"])
        assert result == ["26.260", "26.261", "26.262", "26.270"]

    def test_empty_list(self) -> None:
        result = expand_spec_ranges_batch([])
        assert result == []
