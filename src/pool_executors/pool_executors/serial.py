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
    """Future for serial execution that runs task on first result() call.

    This future does not execute the task immediately when created. Instead,
    the task is executed lazily when result() is first called. Subsequent
    calls return the cached result.

    Attributes:
        _fn: Callable to execute
        _args: Positional arguments for callable
        _kwargs: Keyword arguments for callable
        _result: Cached result after execution
        _exception: Stored exception if task failed
        _done: Flag indicating if task has been executed
        _callbacks: List of callbacks to invoke after execution
    """

    def __init__(self, fn: Callable[..., T], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        """Initialize serial future with callable and arguments.

        Args:
            fn: Callable to execute
            args: Positional arguments
            kwargs: Keyword arguments
        """
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._result: T | None = None
        self._exception: BaseException | None = None
        self._done = False
        self._callbacks: list[Callable[[Future[T]], object]] = []

    def result(self, timeout: float | None = None) -> T:
        """Execute task if not done, return result.

        The timeout parameter is ignored for serial execution as tasks
        run synchronously in the calling thread.

        Args:
            timeout: Ignored for serial execution

        Returns:
            Task result

        Raises:
            Exception: If task raised an exception
        """
        if not self._done:
            try:
                self._result = self._fn(*self._args, **self._kwargs)
            except BaseException as e:
                self._exception = e
            finally:
                self._done = True
                # Invoke callbacks after task completion
                for callback in self._callbacks:
                    try:
                        callback(self)
                    except Exception:
                        logger.exception("Exception in callback")

        if self._exception:
            raise self._exception
        return self._result  # type: ignore[return-value]

    def exception(self, timeout: float | None = None) -> BaseException | None:
        """Return exception raised by task, or None.

        Args:
            timeout: Ignored for serial execution

        Returns:
            Exception if task failed, None otherwise
        """
        if not self._done:
            with contextlib.suppress(BaseException):
                self.result()
        return self._exception

    def done(self) -> bool:
        """Check if task has been executed.

        Returns:
            True if task has been executed, False otherwise
        """
        return self._done

    def cancel(self) -> bool:
        """Attempt to cancel task.

        Serial tasks cannot be cancelled as they execute synchronously.

        Returns:
            Always False
        """
        return False

    def cancelled(self) -> bool:
        """Check if task was cancelled.

        Returns:
            Always False (serial tasks cannot be cancelled)
        """
        return False

    def running(self) -> bool:
        """Check if task is currently running.

        Returns:
            False (serial tasks complete before returning)
        """
        return False

    def add_done_callback(self, fn: Callable[[Future[T]], object]) -> None:
        """Add callback to invoke after task completion.

        If task is already done, callback is invoked immediately.
        Otherwise, it's stored and invoked after task execution.

        Args:
            fn: Callback function taking this future as argument
        """
        if self._done:
            try:
                fn(self)
            except Exception:
                logger.exception("Exception in callback")
        else:
            self._callbacks.append(fn)


class SerialPoolExecutor(Executor):
    """Executor that runs tasks sequentially in the main thread.

    Tasks are collected via submit() but not executed until shutdown()
    is called with wait=True (or when used as context manager).

    This is useful for:
    - Debugging parallel code by forcing serial execution
    - Cases where parallelism overhead exceeds benefits
    - Testing executor-based code without actual parallelism

    Example:
        >>> with SerialPoolExecutor() as executor:
        ...     futures = [executor.submit(func, i) for i in range(10)]
        ...     results = [f.result() for f in futures]
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
        """Submit task for serial execution.

        Task is not executed immediately. It will be executed when
        result() is called on the returned future, or when shutdown(wait=True)
        is called.

        Args:
            fn: Callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            SerialFuture that will execute task lazily

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
        """Shutdown executor and optionally execute pending tasks.

        Args:
            wait: If True, execute all pending tasks. If False, leave tasks unexecuted
            cancel_futures: Ignored (serial tasks cannot be cancelled)
        """
        self._shutdown = True
        if wait:
            # Execute all pending tasks
            for future in self._pending:
                if not future.done():
                    with contextlib.suppress(Exception):
                        # Exceptions are stored in future, will be raised when result() called
                        future.result()

    def __enter__(self) -> SerialPoolExecutor:
        """Enter context manager.

        Returns:
            Self
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, executing all pending tasks.

        Args:
            exc_type: Exception type if exception occurred
            exc_val: Exception value if exception occurred
            exc_tb: Exception traceback if exception occurred
        """
        self.shutdown(wait=True)
