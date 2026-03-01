"""Executor factory with case-insensitive type selection."""

from __future__ import annotations

import logging
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

from pool_executors.pool_executors.serial import SerialPoolExecutor
from pool_executors.pool_executors.types import ExecutorType

try:
    from concurrent.futures import InterpreterPoolExecutor

    HAS_INTERPRETER_POOL_EXECUTOR = True
except ImportError, AttributeError:
    InterpreterPoolExecutor = None  # type: ignore[assignment, misc]
    HAS_INTERPRETER_POOL_EXECUTOR = False

logger = logging.getLogger("pool_executors.factory")


def create_executor(executor_type: ExecutorType | str, **kwargs: Any) -> Executor:
    """Create executor instance based on type.

    Supports case-insensitive type names and aliases:
    - "serial" / "SERIAL" → SerialPoolExecutor
    - "multiprocessing" / "mp" / "MP" → ProcessPoolExecutor
    - "threading" / "thread" / "THREAD" → ThreadPoolExecutor
    - "subinterpreter" / "sub" / "si" / "SI" → InterpreterPoolExecutor (Python 3.14+)

    Args:
        executor_type: Executor type (case-insensitive)
        **kwargs: Arguments forwarded to executor constructor

    Returns:
        Executor instance

    Raises:
        ValueError: If executor_type is invalid

    Example:
        >>> executor = create_executor("mp", max_workers=4)
        >>> executor = create_executor("SERIAL")
        >>> executor = create_executor(ExecutorType.THREADING, max_workers=2)
    """
    # Normalize to lowercase string
    type_str = str(executor_type).lower()

    # Convert to ExecutorType enum
    try:
        exec_type = ExecutorType(type_str)
    except ValueError as e:
        valid_types = ", ".join(sorted({member.value for member in ExecutorType}))
        msg = f"Invalid executor type '{executor_type}'. Valid types: {valid_types}"
        raise ValueError(msg) from e

    # Dispatch to appropriate executor
    if exec_type in (ExecutorType.SERIAL,):
        return SerialPoolExecutor(**kwargs)

    if exec_type in (ExecutorType.MULTIPROCESSING, ExecutorType.MP):
        return ProcessPoolExecutor(**kwargs)

    if exec_type in (ExecutorType.THREADING, ExecutorType.THREAD):
        return ThreadPoolExecutor(**kwargs)

    if exec_type in (ExecutorType.SUBINTERPRETER, ExecutorType.SUB, ExecutorType.SI):
        # Use InterpreterPoolExecutor if available (Python 3.14+)
        if HAS_INTERPRETER_POOL_EXECUTOR and InterpreterPoolExecutor is not None:
            return InterpreterPoolExecutor(**kwargs)
        else:
            logger.warning("InterpreterPoolExecutor not available (Python 3.14+ required), falling back to ProcessPoolExecutor")
            return ProcessPoolExecutor(**kwargs)

    # Should never reach here due to enum validation above
    msg = f"Unhandled executor type: {exec_type}"
    raise RuntimeError(msg)
