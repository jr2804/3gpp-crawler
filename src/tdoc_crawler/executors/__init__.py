"""Parallel executor selection: threads, subinterpreters, processes, or serial."""

from tdoc_crawler.executors.factory import best_executor_type, create_executor, gil_enabled
from tdoc_crawler.executors.serial import SerialPoolExecutor
from tdoc_crawler.executors.types import ExecutorType

__all__ = ["ExecutorType", "SerialPoolExecutor", "best_executor_type", "create_executor", "gil_enabled"]
