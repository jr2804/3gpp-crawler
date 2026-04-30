"""Async-safe utilities for calling async code from sync contexts.

Provides ``run_async`` which safely runs a coroutine regardless of whether
an event loop is already running in the current thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_async[T](coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine from synchronous code.

    Works correctly whether or not an event loop is already running:
    - No running loop: delegates to ``asyncio.run()``.
    - Running loop (e.g. called from async context): runs in a
      background thread that owns its own loop.

    Args:
        coro: Coroutine to execute.

    Returns:
        The coroutine's return value.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
