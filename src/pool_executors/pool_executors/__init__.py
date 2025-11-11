"""Executor pool extensions with serial execution support."""

from pool_executors.factory import create_executor
from pool_executors.serial import SerialPoolExecutor
from pool_executors.types import ExecutorType

__version__ = "0.1.0"

__all__ = ["ExecutorType", "SerialPoolExecutor", "create_executor"]
