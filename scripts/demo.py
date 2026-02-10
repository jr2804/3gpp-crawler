import shutil
import tempfile
import time
from pathlib import Path

from typer.testing import CliRunner

from tdoc_crawler.cli import app
from tdoc_crawler.cli.console import get_console

this_dir = Path(__file__).parent

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


def main() -> None:

    runner = CliRunner()
    console = get_console()
    tmp_dir_args = {"suffix": "tdoc", "dir": this_dir, "delete": True}  # Set to False to inspect cache contents after run
    cache_dir = this_dir / "cache"  # Default cache dir if not using temp dir
    shutil.rmtree(cache_dir, ignore_errors=True)  # Clean up any existing cache dir before run

    # with tempfile.TemporaryDirectory(**tmp_dir_args) as cache_dir:
    common_args = ["--cache-dir", cache_dir, "-v", "debug"]

    # 1. Simply open documents (no metadata crawling)
    for tdoc in TDOCS:
        console.print(f"Testing with {tdoc}...")
        res = runner.invoke(app, ["open", tdoc] + common_args)
        console.print(res.output)

    # wait until documents are opened before testing checkout, to avoid potential race conditions
    time.sleep(5)

    # with tempfile.TemporaryDirectory(**tmp_dir_args) as cache_dir:
    # common_args = ["--cache-dir", cache_dir, "-v", "debug"]

    # 2. Test checkout command (no metadata crawling if not explicitly requested)
    res = runner.invoke(app, ["checkout"] + TDOCS + common_args)
    console.print(res.output)

    # 3. Crawl Meetings
    res = runner.invoke(app, ["crawl-meetings"] + TDOCS + common_args)
    console.print(res.output)

    # 4. Crawl TDocs
    # 5. Query TDocs

    # 6. Simply open spec documents (no metadata crawling)

    # 7. Checkout spec documents (no metadata crawling)

    # 8. Crawl spec metadata

    # 9. Query spec metadata


if __name__ == "__main__":
    main()
