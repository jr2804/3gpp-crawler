"""Executor factory and runtime selection of the fastest available executor."""

from __future__ import annotations

import logging
import sys
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

from tdoc_crawler.executors.serial import SerialPoolExecutor
from tdoc_crawler.executors.types import ExecutorType

try:
    from concurrent.futures import InterpreterPoolExecutor
except ImportError:
    InterpreterPoolExecutor = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


def best_executor_type(*, allow_processes: bool = True) -> ExecutorType:
    """Pick the fastest executor for the running interpreter.

    Order: threads without the GIL, then subinterpreters (3.14+), then processes.
    With ``allow_processes=False`` (e.g. under the stdio MCP server, where spawned
    children deadlock) processes are never chosen; threads are the fallback.
    """
    if not gil_enabled():
        return ExecutorType.THREADING
    if InterpreterPoolExecutor is not None:
        return ExecutorType.SUBINTERPRETER
    return ExecutorType.MULTIPROCESSING if allow_processes else ExecutorType.THREADING


def gil_enabled() -> bool:
    """Return False only on a free-threaded (3.13t/3.14t+) interpreter that runs without the GIL."""
    check = getattr(sys, "_is_gil_enabled", None)
    return True if check is None else bool(check())


def create_executor(executor_type: ExecutorType | str, **kwargs: Any) -> Executor:
    """Create an executor instance for the given type.

    Accepts canonical names and short aliases (case-insensitive):
    - "serial": SerialPoolExecutor (runs tasks synchronously)
    - "multiprocessing" / "mp": ProcessPoolExecutor
    - "threading" / "thread": ThreadPoolExecutor
    - "subinterpreter" / "sub" / "si": InterpreterPoolExecutor (Python 3.14+, else ProcessPoolExecutor)

    Args:
        executor_type: Executor type (canonical name, alias, or ExecutorType member).
        **kwargs: Arguments forwarded to the executor constructor.

    Raises:
        ValueError: If executor_type is invalid.
    """
    exec_type = ExecutorType(executor_type)

    if exec_type is ExecutorType.SERIAL:
        return SerialPoolExecutor(**kwargs)
    if exec_type is ExecutorType.MULTIPROCESSING:
        return ProcessPoolExecutor(**kwargs)
    if exec_type is ExecutorType.THREADING:
        return ThreadPoolExecutor(**kwargs)
    if InterpreterPoolExecutor is not None:
        return InterpreterPoolExecutor(**kwargs)
    logger.warning(
        "ExecutorType.SUBINTERPRETER is not available on Python %s (requires 3.14+); falling back to ProcessPoolExecutor.",
        sys.version_info[:2],
    )
    return ProcessPoolExecutor(**kwargs)
