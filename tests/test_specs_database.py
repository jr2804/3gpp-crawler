"""Tests for specs database helpers."""

from pathlib import Path

from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.models.specs import Specification, SpecificationDownload, SpecificationSourceRecord, SpecificationVersion
from tdoc_crawler.specs.query import SpecQueryFilters


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
    with TDocDatabase(db_path) as database:
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
    with TDocDatabase(db_path) as database:
        database.upsert_specification(spec)
        results = database.query_specs(SpecQueryFilters(spec_numbers=["23.501"]))
    assert results


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
    with TDocDatabase(db_path) as database:
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
    with TDocDatabase(db_path) as database:
        database.upsert_spec_source_record(source_record)
        database.upsert_spec_version(version)
