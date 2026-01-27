"""Adapter to provide aiointerpreters-compatible API using pool_executors."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any, TypeVar

from pool_executors import create_executor

T = TypeVar("T")


class _RunnerContextManager:
    """Context manager for Runner lifecycle."""

    def __init__(self, runner: Runner) -> None:
        self.runner = runner

    def __enter__(self) -> Runner:
        """Start executor and return runner."""
        # Create executor using pool_executors factory
        self.runner._executor = create_executor(self.runner.executor_type, max_workers=self.runner.workers)
        try:
            self.runner._loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create a new one
            self.runner._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.runner._loop)
        return self.runner

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        """Shutdown executor."""
        if self.runner._executor:
            self.runner._executor.shutdown(wait=True)
            self.runner._executor = None
        self.runner._loop = None


class Runner:
    """Adapter that provides aiointerpreters.Runner API using pool_executors."""

    def __init__(self, workers: int = 4, executor_type: str = "subinterpreter") -> None:
        """Initialize runner with specified number of workers.

        Args:
            workers: Number of worker processes/threads
            executor_type: Type of executor ("subinterpreter", "multiprocessing", "threading", "serial")
        """
        self.workers = workers
        self.executor_type = executor_type
        self._executor: Executor | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> _RunnerContextManager:
        """Start executor and return context manager.

        Returns:
            Context manager that yields self
        """
        return _RunnerContextManager(self)

    async def run(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a function in executor and return awaitable result.

        Args:
            func: Function to run in executor
            *args: Positional arguments to pass to function
            **kwargs: Keyword arguments to pass to function

        Returns:
            Result from function execution

        Raises:
            RuntimeError: If runner not started or executor not available
        """
        if self._executor is None:
            raise RuntimeError("Runner not started. Use with runner.start():")
        if self._loop is None:
            raise RuntimeError("Event loop not available")

        # Run function in executor and return awaitable
        return await self._loop.run_in_executor(self._executor, lambda: func(*args, **kwargs))

    def __enter__(self) -> Runner:
        """Context manager entry - not used, use start() instead."""
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        """Context manager exit - not used, use start() instead."""
        pass


__all__ = ["Runner"]
