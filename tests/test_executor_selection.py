"""Tests for TDocCrawler executor selection."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest
from pool_executors import SerialPoolExecutor

from tdoc_crawler.tdocs.operations.crawl import TDocCrawler


def _executor_of(workers: int, executor: str | None) -> tuple[type, str]:
    created, label = TDocCrawler._create_executor_for_workers(workers, executor)
    with created:
        pass
    return type(created), label


def test_auto_single_worker_is_serial() -> None:
    kind, label = _executor_of(1, None)
    assert kind is SerialPoolExecutor
    assert label == "serial"


def test_auto_multi_worker_is_multiprocessing() -> None:
    kind, label = _executor_of(4, None)
    assert kind is ProcessPoolExecutor
    assert label == "multiprocessing"


def test_threading_override() -> None:
    kind, label = _executor_of(4, "threading")
    assert kind is ThreadPoolExecutor
    assert label == "threading"


def test_serial_override_case_insensitive() -> None:
    kind, label = _executor_of(4, "SERIAL")
    assert kind is SerialPoolExecutor
    assert label == "serial"


def test_invalid_executor_raises() -> None:
    with pytest.raises(ValueError, match="Invalid executor type"):
        TDocCrawler._create_executor_for_workers(4, "bogus")
