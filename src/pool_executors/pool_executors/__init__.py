"""Executor pool extensions with serial execution support."""

from .factory import create_executor
from .runner import Runner
from .serial import SerialPoolExecutor
from .types import ExecutorType

__version__ = "0.1.0"

__all__ = ["ExecutorType", "Runner", "SerialPoolExecutor", "create_executor"]
