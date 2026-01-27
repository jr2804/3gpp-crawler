"""Serial executor implementation for sequential task execution."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any, TypeVar

logger = logging.getLogger("pool_executors.serial")

T = TypeVar("T")


class SerialFuture(Future[T]):
    """Future for serial execution that executes immediately.

    This future executes the task immediately upon creation to ensure
    compatibility with as_completed(). The result is cached and returned
    from result() calls.

    This differs from lazy execution but is necessary for as_completed()
    to work correctly, as it waits on internal completion events that are
    only triggered by set_result() or set_exception().
    """

    def __init__(self, fn: Callable[..., T], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """Initialize and immediately execute serial future.

        Args:
            fn: Callable to execute
            args: Positional arguments
            kwargs: Keyword arguments
        """
        super().__init__()

        # Execute immediately and set result/exception
        # This triggers the internal _Waiter event that as_completed() depends on
        try:
            self.set_running_or_notify_cancel()
            result = fn(*args, **kwargs)
            self.set_result(result)
        except BaseException as e:
            self.set_exception(e)


class SerialPoolExecutor(Executor):
    """Executor that runs tasks immediately and sequentially in the main thread.

    Tasks are executed synchronously when submit() is called. This ensures
    compatibility with as_completed() and other concurrent.futures utilities
    that depend on internal completion events.

    This is useful for:
    - Debugging parallel code by forcing serial execution
    - Cases where parallelism overhead exceeds benefits
    - Testing executor-based code without actual parallelism

    Example:
        >>> with SerialPoolExecutor() as executor:
        ...     futures = [executor.submit(func, i) for i in range(10)]
        ...     results = [f.result() for f in futures]  # Already executed
    """

    def __init__(self, max_workers: int | None = None, **kwargs: Any) -> None:
        """Initialize serial executor.

        Args:
            max_workers: Ignored (for API compatibility), logged as debug
            **kwargs: Ignored (for API compatibility)
        """
        if max_workers is not None:
            logger.debug("max_workers=%s ignored for SerialPoolExecutor", max_workers)
        self._pending: list[SerialFuture[Any]] = []
        self._shutdown = False

    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> Future[T]:
        """Submit task for immediate serial execution.

        Task is executed synchronously in the calling thread before this
        method returns. The returned future already contains the result
        or exception.

        Args:
            fn: Callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            SerialFuture with task already executed

        Raises:
            RuntimeError: If executor is shutdown
        """
        if self._shutdown:
            msg = "cannot schedule new futures after shutdown"
            raise RuntimeError(msg)

        future: SerialFuture[T] = SerialFuture(fn, args, kwargs)
        self._pending.append(future)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Shutdown executor.

        All tasks are already executed immediately upon submit(), so this
        method only sets the shutdown flag.

        Args:
            wait: Ignored (tasks already executed)
            cancel_futures: Ignored (serial tasks cannot be cancelled)
        """
        self._shutdown = True

    def __enter__(self) -> SerialPoolExecutor:
        """Enter context manager.

        Returns:
            Self
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager.

        All tasks are already executed, so this just calls shutdown().

        Args:
            exc_type: Exception type if exception occurred
            exc_val: Exception value if exception occurred
            exc_tb: Exception traceback if exception occurred
        """
        self.shutdown(wait=True)
