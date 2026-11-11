"""Tests for runtime executor selection."""

from __future__ import annotations

import sys

import pytest

from tdoc_crawler.executors import ExecutorType, best_executor_type, factory


def test_free_threaded_prefers_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "_is_gil_enabled", lambda: False, raising=False)
    assert best_executor_type() is ExecutorType.THREADING
    assert best_executor_type(allow_processes=False) is ExecutorType.THREADING


def test_gil_without_subinterpreters_uses_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "_is_gil_enabled", lambda: True, raising=False)
    monkeypatch.setattr(factory, "InterpreterPoolExecutor", None)
    assert best_executor_type() is ExecutorType.MULTIPROCESSING


def test_gil_without_subinterpreters_never_picks_processes_for_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "_is_gil_enabled", lambda: True, raising=False)
    monkeypatch.setattr(factory, "InterpreterPoolExecutor", None)
    assert best_executor_type(allow_processes=False) is ExecutorType.THREADING


def test_gil_with_subinterpreters_prefers_subinterpreters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "_is_gil_enabled", lambda: True, raising=False)
    monkeypatch.setattr(factory, "InterpreterPoolExecutor", object)
    assert best_executor_type() is ExecutorType.SUBINTERPRETER
