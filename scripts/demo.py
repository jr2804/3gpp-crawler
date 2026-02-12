import shutil
import tempfile
import time
from pathlib import Path

import typer
from typer.testing import CliRunner

from tdoc_crawler.cli import app
from tdoc_crawler.logging import get_console, get_logger

this_dir = Path(__file__).parent
logger = get_logger(__name__)

# Example data
TDOC1 = "S4-260001"  # docx
TDOC2 = "S4-260002"  # xlsx
TDOC3 = "S4-260003"  # pptx
TDOCS = [TDOC1, TDOC2, TDOC3]

MEETING1 = "SA#123"
MEETING2 = "SA#124"
WORKING_GROUP1 = "RAN#1"
WORKING_GROUP2 = "SA#4"

DATE1 = "2024-01-01"
DATE2 = "2024-02-01"

SPEC1 = "26.130"
SPEC2 = "26.131"
SPEC3 = "26.132"
SPECS = [SPEC1, SPEC2, SPEC3]

runner = CliRunner()
console = get_console()
cache_dir = this_dir / "cache"  # Default cache dir if not using temp dir
common_args = ["--cache-dir", cache_dir, "-v", "debug"]  #


def clean_cache() -> None:
    shutil.rmtree(cache_dir, ignore_errors=True)


def run_command(command: str, args: list[str]) -> None:
    logger.info(f"Running command: {command} with args: {args}")
    res = runner.invoke(app, [command] + args)
    typer.echo(res.output)


def demo_tdocs() -> None:
    clean_cache()

    # 1. Test checkout command (no metadata crawling if not explicitly requested)
    run_command("checkout", TDOCS + common_args)

    # 2. Simply open documents (no metadata crawling)
    for tdoc in TDOCS:
        run_command("open", [tdoc] + common_args)

    # 3. Crawl Meetings run_command("crawl-meetings", TDOCS + common_args)

    # # 4. Crawl TDocs run_command("crawl-tdocs", TDOCS + common_args) # 5. Query TDocs run_command("query-tdocs", ["--tdoc-ids"] + TDOCS + common_args) # 6. Crawl Specs # 7. Query Specs

    # 8. Crawl spec metadata

    # 9. Query spec metadata


def demo_specs() -> None:
    # checkout specs
    res = runner.invoke(app, ["checkout-spec"] + SPECS + common_args)
    # logger.info(res.output)

    # Simply open specs (no metadata crawling)
    for spec in SPECS:
        logger.info(f"Testing with spec {spec}...")
        res = runner.invoke(app, ["open-spec", spec] + common_args)
        typer.echo(res.output)

        break

    # 2. Test checkout command (no metadata crawling if not explicitly requested)
    res = runner.invoke(app, ["checkout"] + TDOCS + common_args)
    # logger.info(res.output)

    # 3. Crawl Meetings
    res = runner.invoke(app, ["crawl-meetings"] + TDOCS + common_args)
    # logger.info(res.output)

    # 4. Crawl TDocs
    # 5. Query TDocs


def main() -> None:

    # tmp_dir_args = {"suffix": "tdoc", "dir": this_dir, "delete": True}  # Set to False to inspect cache contents after run
    #   # Clean up any existing cache dir before run

    # with tempfile.TemporaryDirectory(**tmp_dir_args) as cache_dir:

    # with tempfile.TemporaryDirectory(**tmp_dir_args) as cache_dir:
    # common_args = ["--cache-dir", cache_dir, "-v", "debug"]
    demo_tdocs()
    # demo_specs()

if __name__ == "__main__":
    main()
