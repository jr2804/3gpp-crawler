"""Worker payload handling for work item references during a TDoc crawl."""

from __future__ import annotations

import json

from tdoc_crawler.database.oxyde_models import MeetingMetadata, TDocMetadata
from tdoc_crawler.tdocs.operations.crawl import TDocCrawler


class TestDocumentListPayload:
    """The worker payload carries TDocs plus their 'Related WIs' references."""

    def test_dict_payload_provides_work_items(self) -> None:
        tdoc = TDocMetadata(
            tdoc_id="S4AA260090",
            meeting_id=85916,
            title="[ULBC-MED] On ULBC audio sampling rate",
            source="Orange",
            contact="John",
            agenda_item_nbr="9.6",
        )
        payload = json.dumps(
            {
                "tdocs": [tdoc.model_dump_json()],
                "work_items": {"s4aa260090": ["ulbc-med"]},
            }
        )

        errors: list[str] = []
        parsed = TDocCrawler._parse_document_list_payload(payload, _meeting(), errors)

        assert parsed is not None
        tdocs, work_items, agenda_items = parsed
        assert tdocs == [tdoc.model_dump_json()]
        assert work_items == {"S4AA260090": ["ULBC-MED"]}
        assert agenda_items == {}
        assert errors == []

    def test_legacy_list_payload_has_no_work_items(self) -> None:
        tdoc = TDocMetadata(
            tdoc_id="S4AA260091",
            meeting_id=85916,
            title="Other",
            source="Orange",
            contact="Jane",
            agenda_item_nbr="9.7",
        )

        errors: list[str] = []
        parsed = TDocCrawler._parse_document_list_payload(
            json.dumps([tdoc.model_dump_json()]),
            _meeting(),
            errors,
        )

        assert parsed is not None
        tdocs, work_items, agenda_items = parsed
        assert len(tdocs) == 1
        assert work_items == {}
        assert agenda_items == {}
        assert errors == []

    def test_error_payload_returns_none(self) -> None:
        errors: list[str] = []

        parsed = TDocCrawler._parse_document_list_payload(
            json.dumps({"_error": {"error": "HTTP 404"}}),
            _meeting(),
            errors,
        )

        assert parsed is None
        assert errors
        assert "HTTP 404" in errors[0]

    def test_malformed_work_items_are_ignored(self) -> None:
        payload = json.dumps({"tdocs": [], "work_items": {"S4AA260090": "ULBC-MED"}})

        errors: list[str] = []
        parsed = TDocCrawler._parse_document_list_payload(payload, _meeting(), errors)

        assert parsed == ([], {}, {})
        assert errors == []


def _meeting() -> MeetingMetadata:
    return MeetingMetadata(meeting_id=85916, tbid=375, short_name="SA4-Audio SWG AH")
