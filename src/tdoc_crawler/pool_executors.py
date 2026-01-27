"""Simple pool executors module to provide create_executor function."""

from concurrent.futures import (Executor, ProcessPoolExecutor,
                                ThreadPoolExecutor)
from typing import Literal

ExecutorType = Literal["subinterpreter", "multiprocessing", "threading", "serial"]


def create_executor(executor_type: ExecutorType, max_workers: int | None = None) -> Executor:
    """Create an executor based on the specified type.

    Args:
        executor_type: Type of executor to create
        max_workers: Maximum number of worker threads/processes

    Returns:
        Configured executor instance
    """
    if executor_type == "multiprocessing":
        return ProcessPoolExecutor(max_workers=max_workers)
    elif executor_type == "threading":
        return ThreadPoolExecutor(max_workers=max_workers)
    elif executor_type in ["subinterpreter", "serial"]:
        # For subinterpreter or serial execution, return a ThreadPoolExecutor with 1 worker
        # In a real implementation, subinterpreter would use aiointerpreters
        # For now, we'll use serial execution via single thread
        return ThreadPoolExecutor(max_workers=1)
    else:
        # Default to threading executor
        return ThreadPoolExecutor(max_workers=max_workers)
