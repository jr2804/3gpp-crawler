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
    url_to_safe_stem,
)
from tdoc_crawler.utils.parse import parse_spec_working_group, parse_working_groups


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
        with pytest.raises(ValueError, match="Invalid release format"):
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
        with pytest.raises(ValueError, match="Unknown working group"):
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
        with pytest.raises(ValueError, match="Unknown subgroup code"):
            normalize_subgroup_alias("S99")


class TestParseWorkingGroups:
    """parse_working_groups must reject subgroup codes instead of collapsing them."""

    @pytest.mark.parametrize("value", ["SA4", "S4", "RAN2", "CT1", "sa4", "SA-4", "RAN 2"])
    def test_subgroup_code_rejected(self, value: str) -> None:
        """Regression: 'SA4' silently normalized to SA and crawled the plenary."""
        with pytest.raises(ValueError, match="sub-working group"):
            parse_working_groups([value])

    def test_working_groups_accepted(self) -> None:
        assert parse_working_groups(["SA"]) == [WorkingGroup.SA]
        assert parse_working_groups(["RAN", "SA", "CT"]) == [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]

    def test_defaults_and_inference_unchanged(self) -> None:
        assert parse_working_groups(None) == [WorkingGroup.RAN, WorkingGroup.SA, WorkingGroup.CT]
        assert parse_working_groups(None, ["SA4"]) == [WorkingGroup.SA]


class TestParseSpecWorkingGroup:
    """Specs store the sub-working group, so aliases must resolve to that form."""

    def test_subgroup_aliases_resolve_to_stored_form(self) -> None:
        assert parse_spec_working_group(["SA4"]) == "SA4"
        assert parse_spec_working_group(["S4"]) == "SA4"
        assert parse_spec_working_group(["RAN1"]) == "RAN1"
        assert parse_spec_working_group(["R1"]) == "RAN1"
        assert parse_spec_working_group(["CT3"]) == "CT3"

    def test_plain_working_groups_pass_through(self) -> None:
        assert parse_spec_working_group(["SA"]) == "SA"
        assert parse_spec_working_group(["RAN"]) == "RAN"
        assert parse_spec_working_group(None) is None
        assert parse_spec_working_group(["  "]) is None

    def test_unknown_subgroup_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown sub-working group"):
            parse_spec_working_group(["S99"])


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


class TestUrlToSafeStem:
    """Tests for url_to_safe_stem."""

    def test_https_url_generates_prefix_netloc_hash(self) -> None:
        result = url_to_safe_stem("https://mise.jdx.dev/guide/getting-started")
        assert result.startswith("OTHER_")
        assert "mise.jdx.dev" in result

    def test_different_urls_produce_different_stems(self) -> None:
        url1 = "https://example.com/path/one"
        url2 = "https://example.com/path/two"
        result1 = url_to_safe_stem(url1)
        result2 = url_to_safe_stem(url2)
        assert result1 != result2

    def test_same_path_different_netloc_different_stems(self) -> None:
        url1 = "https://site1.com/page"
        url2 = "https://site2.com/page"
        result1 = url_to_safe_stem(url1)
        result2 = url_to_safe_stem(url2)
        assert result1 != result2

    def test_custom_prefix(self) -> None:
        result = url_to_safe_stem("https://example.com/doc", prefix="DOC_")
        assert result.startswith("DOC_")

    def test_empty_netloc_uses_unknown(self) -> None:
        # urlparse treats "file:///path" as having no netloc
        result = url_to_safe_stem("file:///local/file.txt")
        assert "unknown" in result

    def test_path_only_url(self) -> None:
        # urlparse for just a path-like string
        result = url_to_safe_stem("/home/user/docs/report.pdf")
        # Should handle gracefully (netloc empty)
        assert "OTHER_" in result

    def test_url_with_port(self) -> None:
        result = url_to_safe_stem("https://example.com:8080/path")
        assert "example.com" in result

    def test_url_with_query_params(self) -> None:
        url = "https://example.com/search?q=test&page=1"
        result = url_to_safe_stem(url)
        # Only path is hashed, not query params
        assert "example.com" in result
