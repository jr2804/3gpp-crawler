"""Serial executor for sequential task execution (debugging and tests)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class SerialFuture(Future[T]):
    """Future that executes its callable immediately on creation.

    Executing eagerly keeps ``as_completed()`` working, because it waits on
    completion events that only ``set_result()``/``set_exception()`` trigger.
    """

    def __init__(self, fn: Callable[..., T], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        super().__init__()
        try:
            self.set_running_or_notify_cancel()
            self.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            self.set_exception(exc)


class SerialPoolExecutor(Executor):
    """Executor that runs every task synchronously in the calling thread.

    Useful for debugging parallel code (``--executor serial``) and for tests.

    Example:
        >>> with SerialPoolExecutor() as executor:
        ...     results = [executor.submit(pow, i, 2).result() for i in range(3)]
    """

    def __init__(self, max_workers: int | None = None, **kwargs: Any) -> None:
        if max_workers is not None:
            logger.debug("max_workers=%s ignored for SerialPoolExecutor", max_workers)
        self._shutdown = False

    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> Future[T]:
        if self._shutdown:
            msg = "cannot schedule new futures after shutdown"
            raise RuntimeError(msg)
        return SerialFuture(fn, args, kwargs)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._shutdown = True

    def __enter__(self) -> SerialPoolExecutor:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown(wait=True)
