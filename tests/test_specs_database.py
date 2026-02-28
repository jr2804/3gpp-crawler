"""Tests for specs database helpers."""

from pathlib import Path

from tdoc_crawler.database.specs import SpecDatabase
from tdoc_crawler.specs.models import Specification, SpecificationDownload, SpecificationSourceRecord, SpecificationVersion, SpecQueryFilters


def test_upsert_specification_roundtrip(tmp_path: Path) -> None:
    spec = Specification(
        spec_number="26.132",
        spec_number_compact="26132",
        spec_type="TS",
        title="Spec title",
        status="Release",
        working_group="SA",
        series="26_series",
        latest_version="19.0.0",
    )
    db_path = tmp_path / "tdoc_crawler.db"
    with SpecDatabase(db_path) as database:
        created, changed = database.upsert_specification(spec)
        assert created is True
        assert changed is False


def test_query_specs_returns_results(tmp_path: Path) -> None:
    spec = Specification(
        spec_number="23.501",
        spec_number_compact="23501",
        spec_type="TS",
        title="System architecture",
        status="Release",
        working_group="SA",
        series="23_series",
        latest_version="17.3.0",
    )
    db_path = tmp_path / "tdoc_crawler.db"
    with SpecDatabase(db_path) as database:
        database.upsert_specification(spec)
        results = database.query_specs(SpecQueryFilters(spec_numbers=["23.501"]))
    assert len(results) == 1
    assert results[0].spec_number == "23.501"


def test_query_specs_filters(tmp_path: Path) -> None:
    s1 = Specification(
        spec_number="26.132",
        spec_number_compact="26132",
        spec_type="TS",
        title="Audio Codecs",
        status="Active",
        working_group="SA4",
        series="26_series",
    )
    s2 = Specification(
        spec_number="23.501",
        spec_number_compact="23501",
        spec_type="TS",
        title="System Architecture",
        status="Frozen",
        working_group="SA2",
        series="23_series",
    )
    db_path = tmp_path / "tdoc_crawler.db"

    with SpecDatabase(db_path) as database:
        database.upsert_specification(s1)
        database.upsert_specification(s2)

        # Title filter
        res_title = database.query_specs(SpecQueryFilters(title="audio"))
        assert len(res_title) == 1
        assert res_title[0].spec_number == "26.132"

        # WG filter
        res_wg = database.query_specs(SpecQueryFilters(working_group="SA2"))
        assert len(res_wg) == 1
        assert res_wg[0].spec_number == "23.501"

        # Status filter
        res_status = database.query_specs(SpecQueryFilters(status="Frozen"))
        assert len(res_status) == 1
        assert res_status[0].spec_number == "23.501"


def test_query_specs_discrepancies(tmp_path: Path) -> None:
    spec = Specification(
        spec_number="23.501",
        spec_number_compact="23501",
        spec_type="TS",
        title="System Architecture",
        status="Release",
        working_group="SA",
        series="23_series",
        latest_version="17.3.0",
    )
    record_a = SpecificationSourceRecord(
        spec_number="23.501",
        source_name="3gpp",
        source_identifier="1111",
        metadata_payload={"title": "System Architecture", "status": "Release"},
        versions=["17.3.0"],
        fetched_at=None,
    )
    record_b = SpecificationSourceRecord(
        spec_number="23.501",
        source_name="whatthespec",
        source_identifier="2222",
        metadata_payload={"title": "System Arch", "status": "Release"},
        versions=["17.3.0"],
        fetched_at=None,
    )
    db_path = tmp_path / "tdoc_crawler.db"

    with SpecDatabase(db_path) as database:
        database.upsert_specification(spec)
        database.upsert_spec_source_record(record_a)
        database.upsert_spec_source_record(record_b)

        results = database.query_specs(SpecQueryFilters(spec_numbers=["23.501"]))

    assert len(results) == 1
    differences = results[0].source_differences
    assert "title" in differences
    assert differences["title"]["3gpp"] == "System Architecture"
    assert differences["title"]["whatthespec"] == "System Arch"
    assert "status" not in differences


def test_log_spec_download(tmp_path: Path) -> None:
    checkout_path = tmp_path / "checkout"
    document_path = checkout_path / "23501.docx"
    download = SpecificationDownload(
        spec_number="23.501",
        version="17.3.0",
        download_url="https://example.org/23501.zip",
        checkout_path=checkout_path,
        document_path=document_path,
        attachment_paths=[],
        doc_only_used=True,
        outcome_status="success",
        outcome_message=None,
        extracted_at=None,
    )
    db_path = tmp_path / "tdoc_crawler.db"
    with SpecDatabase(db_path) as database:
        database.log_spec_download(download)


def test_upsert_spec_source_and_version(tmp_path: Path) -> None:
    source_record = SpecificationSourceRecord(
        spec_number="26.132",
        source_name="3gpp",
        source_identifier="12345",
        metadata_payload={"title": "Spec title"},
        versions=["19.0.0"],
        fetched_at=None,
    )
    version = SpecificationVersion(
        spec_number="26.132",
        version="19.0.0",
        file_name="26132-j00.zip",
        source_name="3gpp",
    )
    db_path = tmp_path / "tdoc_crawler.db"
    with SpecDatabase(db_path) as database:
        database.upsert_spec_source_record(source_record)
        database.upsert_spec_version(version)
