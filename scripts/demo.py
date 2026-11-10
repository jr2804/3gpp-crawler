import gc
import shutil
import time
from pathlib import Path

from tdoc_crawler.cli.crawl import crawl_meetings, crawl_tdocs
from tdoc_crawler.cli.query import query_tdocs
from tdoc_crawler.logging import LogLevel, get_console

this_dir = Path(__file__).parent

# Example data
TDOC1 = "S4-260001"  # docx
TDOC2 = "S4-260002"  # xlsx
TDOC3 = "S4-260003"  # pptx
TDOCS = [TDOC1, TDOC2, TDOC3]

console = get_console()
cache_dir = this_dir / "cache"  # Default cache dir if not using temp dir

common_args = {
    "cache_dir": cache_dir,
    "verbosity": "debug",
}


def clean_cache() -> None:
    shutil.rmtree(cache_dir, ignore_errors=True)
    # Small delay to ensure files are released on Windows
    time.sleep(0.5)


def demo_tdocs_crawl() -> None:
    """Demo workflow: crawl meetings -> crawl tdocs -> query tdocs."""
    # start with cleaned cache
    clean_cache()

    # 1. Crawl meetings (last 10 SA4 meetings with files)
    console.print("[cyan]Step 1: Crawling meetings...[/cyan]")
    crawl_meetings(
        subgroup=["SA4"],
        limit_meetings=10,
        cache_dir=cache_dir,
        verbosity=LogLevel.DEBUG,
    )

    # Force garbage collection and delay to release SQLite locks
    gc.collect()
    time.sleep(2)

    # 2. Crawl TDocs (all meetings in database)
    console.print("[cyan]Step 2: Crawling TDocs...[/cyan]")
    crawl_tdocs(workers=1, no_progress=True, **common_args)

    # Force garbage collection and delay to release SQLite locks
    gc.collect()
    time.sleep(2)

    # 3. Query TDocs
    console.print("[cyan]Step 3: Querying TDocs...[/cyan]")
    query_tdocs(tdoc_ids=[TDOC1], **common_args)


def main() -> None:
    demo_tdocs_crawl()


if __name__ == "__main__":
    main()
