"""Executor factory with case-insensitive type selection."""

from __future__ import annotations

import logging
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

from pool_executors.serial import SerialPoolExecutor
from pool_executors.types import ExecutorType

try:
    from concurrent.futures import InterpreterPoolExecutor

    HAS_INTERPRETER_POOL_EXECUTOR = True
except (ImportError, AttributeError):
    InterpreterPoolExecutor = None  # type: ignore[assignment, misc]
    HAS_INTERPRETER_POOL_EXECUTOR = False

logger = logging.getLogger("pool_executors.factory")


def create_executor(executor_type: ExecutorType, **kwargs: Any) -> Executor:
    """Create executor instance based on type.

    Accepts canonical names and short aliases (case-insensitive):
    - "serial" → SerialPoolExecutor
    - "multiprocessing" / "mp" → ProcessPoolExecutor
    - "threading" / "thread" → ThreadPoolExecutor
    - "subinterpreter" / "sub" / "si" → InterpreterPoolExecutor (Python 3.14+)

    Args:
        executor_type: Executor type (canonical name, alias, or ExecutorType member)
        **kwargs: Arguments forwarded to executor constructor

    Returns:
        Executor instance

    Raises:
        ValueError: If executor_type is invalid

    Example:
        >>> executor = create_executor(ExecutorType.THREADING, max_workers=2)
        >>> executor = create_executor("mp", max_workers=4)
        >>> executor = create_executor("SERIAL")
    """
    exec_type = ExecutorType(executor_type)

    if exec_type is ExecutorType.SERIAL:
        return SerialPoolExecutor(**kwargs)

    if exec_type is ExecutorType.MULTIPROCESSING:
        return ProcessPoolExecutor(**kwargs)

    if exec_type is ExecutorType.THREADING:
        return ThreadPoolExecutor(**kwargs)

    if exec_type is ExecutorType.SUBINTERPRETER:
        if HAS_INTERPRETER_POOL_EXECUTOR and InterpreterPoolExecutor is not None:
            return InterpreterPoolExecutor(**kwargs)
        logger.warning("InterpreterPoolExecutor not available (Python 3.14+ required), falling back to ProcessPoolExecutor")
        return ProcessPoolExecutor(**kwargs)

    msg = f"Unhandled executor type: {exec_type}"
    raise RuntimeError(msg)
