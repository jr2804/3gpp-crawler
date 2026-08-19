"""Tests for TDocCrawler executor selection."""

from __future__ import annotations

from concurrent.futures import Executor, ThreadPoolExecutor

import pytest
from pool_executors import ExecutorType, SerialPoolExecutor

from tdoc_crawler.tdocs.operations.crawl import TDocCrawler


def _resolve(workers: int, executor: ExecutorType | None) -> tuple[Executor, ExecutorType]:
    created, resolved = TDocCrawler._create_executor_for_workers(workers, executor)
    with created:
        pass
    return created, resolved


def test_auto_single_worker_is_serial() -> None:
    _, kind = _resolve(1, None)
    assert kind is ExecutorType.SERIAL


def test_auto_multi_worker_is_multiprocessing() -> None:
    _, kind = _resolve(4, None)
    assert kind is ExecutorType.MULTIPROCESSING


def test_threading_override() -> None:
    created, kind = _resolve(4, ExecutorType.THREADING)
    assert isinstance(created, ThreadPoolExecutor)
    assert kind is ExecutorType.THREADING


def test_serial_override_when_workers_high() -> None:
    created, kind = _resolve(4, ExecutorType.SERIAL)
    assert isinstance(created, SerialPoolExecutor)
    assert kind is ExecutorType.SERIAL


def test_alias_mp_resolves_to_multiprocessing() -> None:
    # ExecutorType accepts aliases via _missing_ (case-insensitive)
    assert ExecutorType("mp") is ExecutorType.MULTIPROCESSING
    assert ExecutorType("MP") is ExecutorType.MULTIPROCESSING
    assert ExecutorType("thread") is ExecutorType.THREADING
    assert ExecutorType("si") is ExecutorType.SUBINTERPRETER


def test_invalid_executor_raises() -> None:
    with pytest.raises(ValueError, match="bogus"):
        ExecutorType("bogus")
