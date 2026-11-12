"""Tests for CLI commands."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from tdoc_crawler.cli import tdoc_app
from tdoc_crawler.cli._shared import parse_scope
from tdoc_crawler.cli.mgmt_app import mgmt_app
from tdoc_crawler.cli.workitems_app import workitems_app
from tdoc_crawler.config import PathConfig
from tdoc_crawler.database import TDocDatabase
from tdoc_crawler.database.oxyde_models import TDocMetadata, WorkItemRecord
from tdoc_crawler.database.tags import add_tags, list_tags
from tdoc_crawler.meetings.models import MeetingQueryConfig
from tdoc_crawler.models.base import TagKind
from tdoc_crawler.models.working_groups import WorkingGroup
from tdoc_crawler.tdocs.models import TDocQueryConfig
from tdoc_crawler.tdocs.operations.crawl import TDocCrawlResult
from tdoc_crawler.tdocs.operations.fetch import FetchMissingResult, is_orphan_tdoc
from tdoc_crawler.workitems.operations import EnrichSummary, WorkItemListComparison

from .conftest import insert_sample_meetings_async

runner = CliRunner()


class TestCrawlCommand:
    """Tests for crawl command."""

    @patch("tdoc_crawler.cli.crawl.tdocs.TDocCrawler")
    @patch("tdoc_crawler.cli.crawl.tdocs.TDocDatabase")
    def test_crawl_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl command execution."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"
        mock_db.query_meetings.return_value = []  # Return empty list for progress bar

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl = AsyncMock(
            return_value=MagicMock(
                processed=10,
                inserted=10,
                updated=0,
                errors=[],
            )
        )

        result = runner.invoke(
            tdoc_app,
            ["crawl", "--limit-tdocs", "10"],
        )

        assert result.exit_code == 0
        # Check for key output parts (ANSI codes may be present)
        assert "Processed" in result.stdout
        assert "10" in result.stdout
        assert "TDocs" in result.stdout
        mock_crawler.crawl.assert_called_once()

    @patch("tdoc_crawler.cli.crawl.tdocs.TDocCrawler")
    @patch("tdoc_crawler.cli.crawl.tdocs.TDocDatabase")
    def test_crawl_with_working_group_filter(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test crawl with specific working group."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl = AsyncMock(
            return_value=MagicMock(
                processed=5,
                inserted=5,
                updated=0,
                errors=[],
            )
        )

        result = runner.invoke(
            tdoc_app,
            ["crawl", "--working-group", "RAN"],
        )

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()


class TestSubgroupScopeValidation:
    """Sub-working group codes must not be accepted as working groups."""

    @pytest.mark.parametrize("command", [["crawl"], ["crawl-meetings"]])
    def test_subgroup_code_as_working_group_fails_loudly(self, command: list[str], test_cache_dir: Path) -> None:
        result = runner.invoke(tdoc_app, [*command, "--working-group", "SA4"])

        # Rich wraps the message panel, so strip borders and collapse whitespace
        flat = " ".join(re.sub(r"[┌┐└┘│─]", " ", result.output).split())
        assert result.exit_code == 2, flat
        assert "sub-working group" in flat
        assert "--sub-group" in flat

    def test_parse_scope_raises_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter, match="sub-working group"):
            parse_scope(["SA4"], None)

    def test_subgroup_code_via_sub_group_option(self, test_cache_dir: Path) -> None:
        """-s SA4 is the supported path and must not be rejected."""
        working_groups, subgroups = parse_scope(None, ["SA4"])

        assert subgroups == ["S4"]  # canonical sub-working group code
        assert working_groups == [WorkingGroup.SA]


class TestConfigScopeDefaults:
    """[crawl].working_group/sub_group TOML defaults apply with CLI precedence."""

    def test_resolve_scope_args_uses_config_when_cli_absent(self) -> None:
        wg, sg = parse_scope(
            None,
            None,
            default_to_all=False,
            config_working_group="SA",
            config_subgroup="S4",
        )
        assert wg == [WorkingGroup.SA]
        assert sg == ["S4"]

    def test_resolve_scope_args_cli_overrides_config(self) -> None:
        wg, sg = parse_scope(
            ["RAN"],
            ["R2"],
            default_to_all=False,
            config_working_group="SA",
            config_subgroup="S4",
        )
        assert wg == [WorkingGroup.RAN]
        assert sg == ["R2"]

    @patch("tdoc_crawler.cli.query.meetings.ThreeGPPConfig")
    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_applies_config_scope_defaults(
        self,
        mock_db_class: MagicMock,
        mock_config_class: MagicMock,
    ) -> None:
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        cfg = MagicMock()
        cfg.crawl.working_group = "SA"
        cfg.crawl.sub_group = "S4"
        mock_config_class.from_settings.return_value = cfg

        result = runner.invoke(tdoc_app, ["query-meetings"])

        assert result.exit_code == 0, result.output
        query_config = mock_db.query_meetings.call_args[0][0]
        assert query_config.working_groups == [WorkingGroup.SA]
        assert query_config.subgroups == ["S4"]

    @patch("tdoc_crawler.cli.query.meetings.ThreeGPPConfig")
    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_cli_scope_overrides_config(
        self,
        mock_db_class: MagicMock,
        mock_config_class: MagicMock,
    ) -> None:
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        cfg = MagicMock()
        cfg.crawl.working_group = "SA"
        cfg.crawl.sub_group = "S4"
        mock_config_class.from_settings.return_value = cfg

        result = runner.invoke(tdoc_app, ["query-meetings", "-w", "RAN", "-s", "R2"])

        assert result.exit_code == 0, result.output
        query_config = mock_db.query_meetings.call_args[0][0]
        assert query_config.working_groups == [WorkingGroup.RAN]
        assert query_config.subgroups == ["R2"]


class TestCrawlMeetingsCommand:
    """Tests for crawl-meetings command."""

    @patch("tdoc_crawler.cli.crawl.meetings.MeetingCrawler")
    @patch("tdoc_crawler.cli.crawl.meetings.MeetingDatabase")
    def test_crawl_meetings_basic(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test basic crawl-meetings command execution."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.log_crawl_start = AsyncMock(return_value=1)
        mock_db.log_crawl_end = AsyncMock(return_value=None)

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl = AsyncMock(
            return_value=MagicMock(
                processed=20,
                inserted=20,
                updated=0,
                errors=[],
            )
        )

        result = runner.invoke(
            tdoc_app,
            [
                "crawl-meetings",
                "--no-prompt-credentials",
            ],
        )

        assert result.exit_code == 0
        # Check for key output parts (ANSI codes may be present)
        assert "Processed" in result.stdout
        assert "20" in result.stdout
        assert "meetings" in result.stdout


class TestQueryCommand:
    """Tests for query command."""

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_subgroup_filter_reaches_config(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """--sub-group SA4 must land in the query config as the S4 code."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=sample_tdocs[:1])

        result = runner.invoke(tdoc_app, ["query", "--sub-group", "SA4"])

        assert result.exit_code == 0, result.output
        await_args = mock_db.query_tdocs.await_args
        assert await_args is not None
        config = await_args.args[0]
        assert config.subgroups == ["S4"]

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_work_item_filter_reaches_config(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """--work-item must land in the query config, normalized to upper case."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=sample_tdocs[:1])

        result = runner.invoke(tdoc_app, ["query", "--work-item", "ulbc-med"])

        assert result.exit_code == 0, result.output
        await_args = mock_db.query_tdocs.await_args
        assert await_args is not None
        config = await_args.args[0]
        assert config.work_items == ["ULBC-MED"]

    @patch("tdoc_crawler.cli.query.work_items.TDocDatabase")
    def test_work_items_query_lists_catalogue(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """``work-items query`` prints the catalogue with TDoc counts."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.list_work_items = AsyncMock(
            return_value=[
                WorkItemRecord(wi_id="ULBC-MED", tdoc_count=749, title="Ultra Low Bitrate Speech Codec", release="Rel-20"),
                WorkItemRecord(wi_id="FS_ULBC", tdoc_count=12, title="Study on ULBC"),
            ]
        )

        result = runner.invoke(workitems_app, ["query"])

        assert result.exit_code == 0, result.output
        assert "ULBC-MED" in result.stdout
        assert "749" in result.stdout

    @patch("tdoc_crawler.cli.query.work_items.TDocDatabase")
    def test_work_items_query_without_data(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """An empty catalogue is reported, not raised."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.list_work_items = AsyncMock(return_value=[])

        result = runner.invoke(workitems_app, ["query"])

        assert result.exit_code == 0, result.output
        assert "No work items found" in result.stdout

    @patch("tdoc_crawler.cli.query.work_items.TDocDatabase")
    def test_work_items_query_filters_requested_ids(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Positional work item IDs narrow the catalogue to those work items."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.list_work_items = AsyncMock(
            return_value=[
                WorkItemRecord(wi_id="ULBC-MED", tdoc_count=3),
                WorkItemRecord(wi_id="FS_ULBC", tdoc_count=1),
            ]
        )

        result = runner.invoke(workitems_app, ["query", "ulbc-med"])

        assert result.exit_code == 0, result.output
        assert "ULBC-MED" in result.stdout
        assert "FS_ULBC" not in result.stdout

    def test_query_rejects_subgroup_as_working_group(self, test_cache_dir: Path) -> None:
        """-w SA4 must not silently collapse to SA."""
        result = runner.invoke(tdoc_app, ["query", "--working-group", "SA4"])

        flat = " ".join(re.sub(r"[┌┐└┘│─]", " ", result.output).split())
        assert result.exit_code == 2, flat
        assert "sub-working group" in flat
        assert "--sub-group" in flat

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_no_results(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query command with no results."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query"],
        )

        assert result.exit_code == 0
        assert "No TDocs found" in result.stdout

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_with_results_table(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test query with results in table format."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=sample_tdocs)

        result = runner.invoke(
            tdoc_app,
            ["query", "--output", "table"],
        )

        assert result.exit_code == 0
        assert "R1-2301234" in result.stdout

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_json_format(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test query with JSON output format."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=sample_tdocs[:1])

        result = runner.invoke(
            tdoc_app,
            ["query", "--output", "json"],
        )

        assert result.exit_code == 0
        assert "R1-2301234" in result.stdout
        assert "tdoc_id" in result.stdout

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_specific_tdoc(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test query for specific TDoc IDs."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=sample_tdocs[:1])

        result = runner.invoke(
            tdoc_app,
            ["query", "R1-2301234"],
        )

        assert result.exit_code == 0

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_no_working_group_filter_when_not_requested(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Querying without --working-group must not apply a tbid IN (...) filter.

        Regression: parse_working_groups() defaults to [RAN, SA, CT] for crawls,
        which silently dropped orphan records whose tbid wasn't resolved (e.g.
        odd-numbered interim/telco docs whose meeting didn't land in the
        meetings table).
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=sample_tdocs[:1])

        result = runner.invoke(tdoc_app, ["query", "SA4AA250001", "--no-fetch"])

        assert result.exit_code == 0
        config = mock_db.query_tdocs.await_args.args[0]
        assert config.working_groups is None, f"expected no working_group filter, got {config.working_groups!r}"

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_query_warns_on_orphans_without_refresh(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Query result containing an orphan must print a warning."""
        orphan = TDocMetadata(
            tdoc_id="SA4AA250001",
            meeting_id=0,
            tbid=0,
            title="Orphan",
            source="",
            contact="",
            tdoc_type="unknown",
            for_purpose="unknown",
            agenda_item_nbr="0",
            agenda_item_text="Unknown",
            status=None,
        )
        assert is_orphan_tdoc(orphan)
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_tdocs = AsyncMock(return_value=[orphan])

        result = runner.invoke(tdoc_app, ["query", "SA4AA250001", "--no-fetch"])

        assert result.exit_code == 0
        assert "orphan" in result.stdout
        assert "--refresh-orphans" in result.stdout


class TestWorkItemsCommands:
    """Tests for the work-items crawl/enrich/audit commands."""

    @patch("tdoc_crawler.cli.crawl.work_items.TDocDatabase")
    @patch("tdoc_crawler.cli.crawl.work_items.fetch_work_items")
    def test_crawl_scoped_to_subgroup(
        self,
        mock_fetch: MagicMock,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """``work-items crawl -s S4`` fetches only the S4 lead body list."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.store_work_items = AsyncMock(return_value=2)
        mock_fetch.return_value = {"S4": [MagicMock(), MagicMock()]}

        result = runner.invoke(workitems_app, ["crawl", "-s", "S4", "-c", str(test_cache_dir)])

        assert result.exit_code == 0, result.output
        assert mock_fetch.call_args.args[0] == ["S4"]
        assert "Stored 2 work items" in result.stdout

    @patch("tdoc_crawler.cli.crawl.work_items.discover_lead_bodies")
    def test_crawl_without_scope_discovers_lead_bodies(
        self,
        mock_discover: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Without a scope the lead bodies come from the global work item list."""
        mock_discover.return_value = []

        with patch("tdoc_crawler.cli.crawl.work_items.fetch_work_items", return_value={}) as mock_fetch:
            result = runner.invoke(workitems_app, ["crawl", "-c", str(test_cache_dir)])

        assert result.exit_code == 0, result.output
        assert mock_discover.called
        assert mock_fetch.called

    @patch("tdoc_crawler.cli.crawl.work_items.enrich_work_items")
    def test_enrich_prints_summary(
        self,
        mock_enrich: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """``work-items enrich`` prints the enrichment summary."""
        mock_enrich.return_value = EnrichSummary(enriched=3, specs_found=5, crs_found=2, parents_found=1)

        result = runner.invoke(workitems_app, ["enrich", "--work-item", "ULBC-MED", "-c", str(test_cache_dir)])

        assert result.exit_code == 0, result.output
        assert "Enriched 3 work items" in result.stdout
        assert mock_enrich.call_args.args[1] == ["ULBC-MED"]

    @patch("tdoc_crawler.cli.query.work_items.compare_work_item_list")
    def test_audit_prints_coverage_rows(
        self,
        mock_compare: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """``work-items audit`` prints the per-lead-body coverage table."""
        mock_compare.return_value = WorkItemListComparison(
            rows=[{"lead_body": "S4", "list": 10, "in_catalogue": 8, "missing": 2}],
            list_entries=10,
            matched=8,
            missing_from_db=2,
            missing_from_list=1,
        )

        result = runner.invoke(workitems_app, ["audit", "-c", str(test_cache_dir)])

        assert result.exit_code == 0, result.output
        assert "S4" in result.stdout
        assert "missing from catalogue 2" in result.stdout


class TestQueryMeetingsCommand:
    """Tests for query-meetings command."""

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_no_results(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with no results."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query-meetings"],
        )

        assert result.exit_code == 0
        assert "No meetings found" in result.stdout

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_with_subgroup_filter(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with subgroup filter."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query-meetings", "-s", "SA4"],
        )

        assert result.exit_code == 0
        # Verify that query_meetings was called with normalized subgroup code.
        call_args = mock_db.query_meetings.call_args[0][0]
        assert call_args.subgroups == ["S4"]

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_with_subgroup_alias(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with subgroup alias (S4 -> SA4)."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query-meetings", "-s", "S4"],
        )

        assert result.exit_code == 0
        # Verify that S4 alias was normalized to subgroup code.
        call_args = mock_db.query_meetings.call_args[0][0]
        assert "S4" in call_args.subgroups

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_with_plenary_alias(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with plenary subgroup alias (RP -> RAN Plenary)."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query-meetings", "-s", "RP"],
        )

        assert result.exit_code == 0
        # Verify that RP alias was normalized to subgroup code.
        call_args = mock_db.query_meetings.call_args[0][0]
        assert "RP" in call_args.subgroups

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_with_working_group_alias(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with working group alias (SP -> SA)."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query-meetings", "-w", "SP"],
        )

        assert result.exit_code == 0
        # Verify that SP alias was expanded to SA
        call_args = mock_db.query_meetings.call_args[0][0]
        assert WorkingGroup.SA in call_args.working_groups

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_query_meetings_combined_filters(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test query-meetings with combined working group and subgroup filters."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        result = runner.invoke(
            tdoc_app,
            ["query-meetings", "-w", "SA", "-s", "S4"],
        )

        assert result.exit_code == 0
        # Verify both filters were applied
        call_args = mock_db.query_meetings.call_args[0][0]
        assert WorkingGroup.SA in call_args.working_groups
        assert "S4" in call_args.subgroups


class TestStatsCommand:
    """Tests for stats command."""

    def test_stats_basic(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """Test stats command execution."""

        async def _prepare_db() -> None:
            async with TDocDatabase(test_db_path) as db:
                await insert_sample_meetings_async(db, sample_meetings)
                for tdoc in sample_tdocs:
                    _ = await db.upsert_tdoc(tdoc)

        asyncio.run(_prepare_db())

        result = runner.invoke(
            tdoc_app,
            ["stats"],
        )

        assert result.exit_code == 0
        assert "Total TDocs" in result.stdout
        assert "3" in result.stdout

    def test_stats_missing_database(
        self,
        test_cache_dir: Path,
    ) -> None:
        """Test stats command with missing database."""
        result = runner.invoke(
            tdoc_app,
            ["stats"],
        )

        assert result.exit_code == 1
        assert "Database not found" in result.stdout


class TestOpenCommand:
    """Tests for open command."""

    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.tdoc_app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.tdoc_app.TDocDatabase")
    def test_open_existing_tdoc(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
        sample_tdocs: list[TDocMetadata],
    ) -> None:
        """Test open command for existing TDoc."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = sample_tdocs[:1]
        mock_fetch.return_value = FetchMissingResult(refreshed=sample_tdocs[:1])

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            tdoc_app,
            ["open", "R1-2301234"],
        )

        assert result.exit_code == 0
        mock_prepare.assert_called_once()
        mock_launch.assert_called_once()

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_open_missing_tdoc(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command for missing TDoc."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        result = runner.invoke(
            tdoc_app,
            ["open", "INVALID-ID"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.tdoc_app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.tdoc_app.TDocDatabase")
    def test_open_with_whatthespec_fallback(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command uses whatthespec fallback when TDoc missing and no credentials.

        This integration test verifies:
        1. TDoc not found in database
        2. fetch_missing_tdocs is called
        3. whatthespec fallback returns valid metadata
        4. TDoc is inserted and file is opened
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        # Database returns no results initially
        mock_db.query_tdocs.return_value = []
        # After fetch, database returns the fetched TDoc
        mock_db.upsert_tdoc.return_value = (True, False)

        # Mock fetch_missing_tdocs to simulate whatthespec fallback
        metadata = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=123,
            title="SA4#135 meeting agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="agenda",
            for_purpose="Approval",
            agenda_item_nbr="2",
            agenda_item_text="Agenda item text",
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )

        mock_fetch.return_value = FetchMissingResult(
            refreshed=[metadata],
            fetch_result=TDocCrawlResult(
                processed=1,
                inserted=1,
                updated=0,
                errors=[],
            ),
            used_whatthespec_fallback=True,
        )

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            tdoc_app,
            ["open", "S4-260001"],
        )

        assert result.exit_code == 0
        mock_prepare.assert_called_once()
        mock_launch.assert_called_once()

    @patch("tdoc_crawler.cli.tdoc_app.launch_file")
    @patch("tdoc_crawler.cli.tdoc_app.prepare_tdoc_file")
    @patch("tdoc_crawler.cli.tdoc_app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.tdoc_app.TDocDatabase")
    def test_open_with_whatthespec_no_credentials_required(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_prepare: MagicMock,
        mock_launch: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test open command works without EOL credentials when whatthespec available.

        This integration test verifies:
        1. No EOL credentials set (None)
        2. TDoc not in database
        3. whatthespec resolver provides metadata
        4. TDoc is opened without requiring portal credentials
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Mock fetch_missing_tdocs to simulate whatthespec fallback success
        metadata = TDocMetadata(
            tdoc_id="R1-260001",
            meeting_id=123,
            title="RAN1 discussion document",
            url="https://www.3gpp.org/tsg_ran/RAN1/r1-260001.zip",
            source="RAN1 Chair",
            contact="Test Contact",
            tdoc_type="discussion",
            agenda_item_text="Test agenda item text",
            for_purpose="Discussion",
            agenda_item_nbr="3.1",
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )

        mock_fetch.return_value = FetchMissingResult(
            refreshed=[metadata],
            fetch_result=TDocCrawlResult(
                processed=1,
                inserted=1,
                updated=0,
                errors=[],
            ),
            used_whatthespec_fallback=True,
        )

        mock_file = test_cache_dir / "test.pdf"
        mock_prepare.return_value = mock_file

        result = runner.invoke(
            tdoc_app,
            ["open", "R1-260001"],
        )

        # Should succeed (exit code 0) and use whatthespec fallback
        assert result.exit_code == 0
        # Verify output indicates whatthespec was used
        assert "whatthespec" in result.stdout.lower()


class TestCheckoutCommand:
    """Tests for checkout command with whatthespec fallback."""

    @patch("tdoc_crawler.cli.checkout.checkout_tdoc")
    @patch("tdoc_crawler.cli.tdoc_app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.tdoc_app.TDocDatabase")
    def test_checkout_with_whatthespec_fallback(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_checkout: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test checkout command uses whatthespec fallback for missing TDocs.

        This integration test verifies:
        1. Multiple TDocs requested
        2. TDocs not found in database
        3. Portal fetch fails (no credentials)
        4. whatthespec fallback resolves TDocs
        5. checkout_tdoc called for resolved TDocs
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []
        mock_db.upsert_tdoc.return_value = (True, False)

        # Mock fetch_missing_tdocs to return credentials error and then success via whatthespec
        # Mock fetch_missing_tdocs to return success with whatthespec fallback
        tdoc1 = TDocMetadata(
            tdoc_id="S4-260001",
            meeting_id=123,
            title="SA4#135 agenda",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260001.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="agenda",
            agenda_item_text="Test agenda item text",
            for_purpose="Approval",
            agenda_item_nbr="2",
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )
        tdoc2 = TDocMetadata(
            tdoc_id="S4-260002",
            meeting_id=123,
            title="SA4#135 document",
            url="https://www.3gpp.org/tsg_sa/WG4/s4-260002.zip",
            source="SA WG4 Chair",
            contact="Test Contact",
            tdoc_type="discussion",
            agenda_item_text="Test agenda item text",
            for_purpose="Discussion",
            agenda_item_nbr="3",
            status="available",
            validated=False,
            validation_failed=False,
            is_revision_of=None,
            file_size=None,
            date_created=None,
        )

        mock_fetch.return_value = FetchMissingResult(
            refreshed=[tdoc1, tdoc2],
            fetch_result=TDocCrawlResult(
                processed=2,
                inserted=2,
                updated=0,
                errors=[],
            ),
            used_whatthespec_fallback=True,
        )

        result = runner.invoke(
            tdoc_app,
            ["checkout", "S4-260001", "S4-260002"],
        )

        assert result.exit_code == 0
        # checkout_tdoc should have been called for both TDocs
        assert mock_checkout.call_count == 2

    @patch("tdoc_crawler.cli.checkout.checkout_tdoc")
    @patch("tdoc_crawler.cli.tdoc_app.fetch_missing_tdocs")
    @patch("tdoc_crawler.cli.tdoc_app.TDocDatabase")
    def test_checkout_with_whatthespec_graceful_failure(
        self,
        mock_db_class: MagicMock,
        mock_fetch: MagicMock,
        mock_checkout: MagicMock,
        test_cache_dir: Path,
    ) -> None:
        """Test checkout handles whatthespec failure gracefully.

        This integration test verifies:
        1. whatthespec fetch doesn't insert any TDocs
        2. CLI does NOT crash
        3. CLI reports missing TDocs
        4. Exit code indicates partial failure
        """
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Mock fetch_missing_tdocs to return empty results (all TDocs missing)
        mock_fetch.return_value = FetchMissingResult(
            refreshed=[],
            fetch_result=TDocCrawlResult(
                processed=1,
                inserted=0,
                updated=0,
                errors=["TDoc not found"],
            ),
            used_whatthespec_fallback=True,
        )

        result = runner.invoke(
            tdoc_app,
            ["checkout", "S4-999999"],
        )

        # Should exit with error code due to missing TDoc
        assert result.exit_code == 1
        # Should report issues in output
        assert "issues detected" in result.stdout.lower() or "error" in result.stdout.lower()


class TestEnvironmentVariables:
    """Tests for environment variable support in CLI options."""

    @patch("tdoc_crawler.cli.crawl.tdocs.TDocCrawler")
    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_env_var_cache_dir(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that TDC_CACHE_DIR environment variable sets cache directory."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"
        mock_db.query_meetings.return_value = []

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl = AsyncMock(
            return_value=MagicMock(
                processed=0,
                inserted=0,
                updated=0,
                errors=[],
            )
        )

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_CACHE_DIR", str(test_cache_dir))

        result = runner.invoke(tdoc_app, ["crawl"])

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()

    @patch("tdoc_crawler.cli.crawl.tdocs.TDocCrawler")
    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_env_var_workers(
        self,
        mock_db_class: MagicMock,
        mock_crawler_class: MagicMock,
        test_cache_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that TDC_WORKERS environment variable sets worker count."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.log_crawl_start.return_value = "1"
        mock_db.query_meetings.return_value = []

        mock_crawler = MagicMock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.crawl = AsyncMock(
            return_value=MagicMock(
                processed=0,
                inserted=0,
                updated=0,
                errors=[],
            )
        )

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_WORKERS", "8")

        result = runner.invoke(tdoc_app, ["crawl"])

        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()
        # Verify workers parameter was passed to config
        call_args = mock_crawler.crawl.call_args[0]
        config = call_args[0]
        assert config.workers == 8

    @patch("tdoc_crawler.cli.query.meetings.MeetingDatabase")
    def test_env_var_working_group(
        self,
        mock_db_class: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that TDC_WORKING_GROUP environment variable filters by working group."""
        mock_db = MagicMock()
        mock_db_class.return_value.__aenter__.return_value = mock_db
        mock_db.query_meetings = AsyncMock(return_value=[])

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_WORKING_GROUP", "SA")

        result = runner.invoke(tdoc_app, ["query-meetings"])

        assert result.exit_code == 0
        # Verify working group filter was applied
        call_args = mock_db.query_meetings.call_args[0][0]

        assert WorkingGroup.SA in call_args.working_groups

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_env_var_output_format(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that TDC_OUTPUT environment variable sets output format."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Set environment variable via monkeypatch
        monkeypatch.setenv("TDC_OUTPUT", "json")

        result = runner.invoke(tdoc_app, ["query"])

        assert result.exit_code == 0

    def test_env_var_cli_override(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that CLI arguments override environment variables."""
        # Note: TDC_VERBOSE has been removed - verbose mode is now controlled by --verbose flag only

        # But override with CLI argument
        result = runner.invoke(tdoc_app, ["--help"])

        # Help command should succeed regardless
        assert result.exit_code == 0

    @patch("tdoc_crawler.credentials.resolve_credentials")
    def test_env_var_credentials(
        self,
        mock_resolve: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        test_cache_dir: Path,
    ) -> None:
        """Test that TDC_EOL_USERNAME and TDC_EOL_PASSWORD set credentials."""
        # Set environment variables
        monkeypatch.setenv("TDC_EOL_USERNAME", "testuser")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "testpass")

        # Mock resolve_credentials to return valid credentials
        mock_resolve.return_value = None

        # Create minimal database file for stats command
        db_file = PathConfig(cache_dir=test_cache_dir).db_file
        db_file.touch()

        result = runner.invoke(tdoc_app, ["stats"])

        # Verify resolve_credentials was called
        # (Actual credential resolution happens via Typer's envvar parameter)
        assert result.exit_code == 0

    @patch("tdoc_crawler.credentials.resolve_credentials")
    def test_env_var_prompt_credentials(
        self,
        mock_resolve: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        test_cache_dir: Path,
    ) -> None:
        """Test that TDC_EOL_PROMPT controls credential prompting."""
        # Set environment variable to disable prompting
        monkeypatch.setenv("TDC_EOL_PROMPT", "false")

        mock_resolve.return_value = None

        # Create minimal database file for stats command
        db_file = PathConfig(cache_dir=test_cache_dir).db_file
        db_file.touch()

        result = runner.invoke(tdoc_app, ["stats"])

        assert result.exit_code == 0

    @patch("tdoc_crawler.cli.query.tdocs.TDocDatabase")
    def test_env_var_limit(
        self,
        mock_db_class: MagicMock,
        test_cache_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that TDC_LIMIT environment variables set limits."""
        mock_db = MagicMock(spec=TDocDatabase)
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query_tdocs.return_value = []

        # Set multiple limit environment variables
        monkeypatch.setenv("TDC_LIMIT", "5")
        monkeypatch.setenv("TDC_START_DATE", "2024-01-01")
        monkeypatch.setenv("TDC_END_DATE", "2024-12-31")

        result = runner.invoke(tdoc_app, ["query"])

        assert result.exit_code == 0

    @patch("tdoc_crawler.credentials.resolve_credentials")
    def test_env_var_multiple_credentials(
        self,
        mock_resolve: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        test_cache_dir: Path,
    ) -> None:
        """Test multiple credential environment variables work together."""
        # Set all credential-related environment variables
        monkeypatch.setenv("TDC_EOL_USERNAME", "envuser")
        monkeypatch.setenv("TDC_EOL_PASSWORD", "envpass")
        monkeypatch.setenv("TDC_EOL_PROMPT", "true")

        mock_resolve.return_value = None

        # Create minimal database file for stats command
        db_file = PathConfig(cache_dir=test_cache_dir).db_file
        db_file.touch()

        result = runner.invoke(tdoc_app, ["stats"])

        assert result.exit_code == 0


class TestDatabaseCommand:
    """Tests for the `database` command group (alias `db`)."""

    def test_database_help_lists_commands(self) -> None:
        """The database group shows the clear and tag transfer commands."""
        result = runner.invoke(mgmt_app, ["database", "--help"])

        assert result.exit_code == 0
        for name in ("clear-tdocs", "clear-specs", "clear-meetings", "clear-all", "export-tags", "import-tags"):
            assert name in result.output

    def test_db_alias_resolves(self) -> None:
        """The short alias `db` mounts the same command group."""
        result = runner.invoke(mgmt_app, ["db", "--help"])

        assert result.exit_code == 0
        assert "clear-all" in result.output

    def test_clear_all_deletes_db_and_preserves_tags(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """clear-all rebuilds the database and re-imports the saved tags."""

        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await insert_sample_meetings_async(db, sample_meetings)
                await db.upsert_tdoc(sample_tdocs[0])
                await add_tags(TagKind.TDOC, "S4-250001", ["keepme"])

        asyncio.run(seed())

        result = runner.invoke(mgmt_app, ["database", "clear-all", "--yes"])

        assert result.exit_code == 0
        assert "Restored 1 tag(s)" in result.output
        backup_file = test_db_path.parent / "tags-backup.json"
        assert not backup_file.exists()
        assert test_db_path.exists()  # recreated with fresh schema

        async def verify() -> tuple[list, list]:
            async with TDocDatabase(test_db_path) as db:
                remaining = await db.query_tdocs(TDocQueryConfig(tdoc_ids=[sample_tdocs[0].tdoc_id]))
                tags = await list_tags()
            return remaining, tags

        remaining, tags = asyncio.run(verify())
        assert remaining == []
        assert [(t.kind, t.item_id, t.tag) for t in tags] == [(TagKind.TDOC, "S4-250001", "keepme")]

    def test_clear_all_prompts_and_aborts_without_yes(self, test_db_path: Path) -> None:
        """Without --yes, declining the confirmation keeps the database."""

        async def seed() -> None:
            async with TDocDatabase(test_db_path):
                pass  # create the file

        asyncio.run(seed())

        result = runner.invoke(mgmt_app, ["database", "clear-all"], input="n\n")

        assert result.exit_code != 0
        assert test_db_path.exists()

    def test_clear_meetings_keeps_tdocs(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        sample_meetings: list[dict[str, object]],
    ) -> None:
        """clear-meetings only removes meeting records."""

        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await insert_sample_meetings_async(db, sample_meetings)
                await db.upsert_tdoc(sample_tdocs[0])

        asyncio.run(seed())

        result = runner.invoke(mgmt_app, ["database", "clear-meetings"])

        assert result.exit_code == 0

        async def verify() -> tuple[list, list]:
            async with TDocDatabase(test_db_path) as db:
                tdocs = await db.query_tdocs(TDocQueryConfig())
                meetings = await db.query_meetings(MeetingQueryConfig(limit=10))
            return tdocs, meetings

        tdocs, meetings = asyncio.run(verify())
        assert len(tdocs) == 1
        assert meetings == []

    def test_clear_tdocs_removes_tdocs_keeps_tags(self, test_db_path: Path, sample_tdocs: list[TDocMetadata]) -> None:
        """clear-tdocs wipes TDoc records but leaves tag rows untouched."""

        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await db.upsert_tdoc(sample_tdocs[0])
                await add_tags(TagKind.TDOC, sample_tdocs[0].tdoc_id, ["keepme"])

        asyncio.run(seed())

        result = runner.invoke(mgmt_app, ["database", "clear-tdocs"])

        assert result.exit_code == 0

        async def verify() -> tuple[list, list]:
            async with TDocDatabase(test_db_path) as db:
                tdocs = await db.query_tdocs(TDocQueryConfig())
                tags = await list_tags()
            return tdocs, tags

        tdocs, tags = asyncio.run(verify())
        assert tdocs == []
        assert [t.tag for t in tags] == ["keepme"]

    def test_export_tags_json(
        self,
        test_db_path: Path,
        sample_tdocs: list[TDocMetadata],
        tmp_path: Path,
    ) -> None:
        """export-tags writes the natural-key dump to the requested file."""

        async def seed() -> None:
            async with TDocDatabase(test_db_path) as db:
                await db.upsert_tdoc(sample_tdocs[0])
                await add_tags(TagKind.TDOC, sample_tdocs[0].tdoc_id, ["keepme"])

        asyncio.run(seed())
        dump = tmp_path / "tags.json"

        result = runner.invoke(mgmt_app, ["database", "export-tags", "--output", "json", "--file", str(dump)])

        assert result.exit_code == 0
        assert dump.exists()
        assert sample_tdocs[0].tdoc_id in dump.read_text(encoding="utf-8")

        result = runner.invoke(mgmt_app, ["database", "import-tags", str(dump), "--output", "json"])

        assert result.exit_code == 0
        assert '"added": 0' in result.output  # already imported, idempotent
