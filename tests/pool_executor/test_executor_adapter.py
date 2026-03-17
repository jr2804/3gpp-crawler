"""Tests for executor adapter that provides aiointerpreters-compatible API."""

from __future__ import annotations

import asyncio

import pytest
from pool_executors import Runner


class TestRunner:
    """Tests for Runner adapter class."""

    def test_runner_initialization(self) -> None:
        """Test runner initialization with default and custom parameters."""
        # Default initialization (defaulted to multiprocessing for stability)
        runner = Runner()
        assert runner.workers == 4
        assert runner.executor_type == "multiprocessing"
        assert runner._executor is None
        assert runner._loop is None

        # Custom initialization
        runner = Runner(workers=8, executor_type="threading")
        assert runner.workers == 8
        assert runner.executor_type == "threading"

    def test_start_context_manager(self) -> None:
        """Test that start() creates and manages executor lifecycle."""
        runner = Runner(workers=2, executor_type="threading")

        with runner.start() as started_runner:
            assert started_runner is runner
            assert runner._executor is not None
            assert runner._loop is not None

        # Verify executor was shutdown
        assert runner._executor is None
        assert runner._loop is None

    def test_run_function_in_executor(self) -> None:
        """Test running functions asynchronously in executor."""

        # Mock function to run
        def test_function(x: int, y: int) -> int:
            return x + y

        runner = Runner(workers=2, executor_type="threading")

        async def test_async() -> int:
            with runner.start() as started_runner:
                result = await started_runner.run(test_function, 3, 4)
                return result

        # Run the async test
        result = asyncio.run(test_async())

        # Verify function was called correctly
        assert result == 7

    def test_run_function_with_kwargs(self) -> None:
        """Test running functions with keyword arguments."""

        # Mock function that uses kwargs
        def test_function(x: int, y: int, multiplier: int = 1) -> int:
            return (x + y) * multiplier

        runner = Runner(workers=2, executor_type="threading")

        async def test_async() -> int:
            with runner.start() as started_runner:
                result = await started_runner.run(test_function, 3, 4, multiplier=2)
                return result

        # Run the async test
        result = asyncio.run(test_async())

        # Verify function was called with correct arguments
        assert result == 14  # (3 + 4) * 2

    def test_run_without_start_raises_error(self) -> None:
        """Test that calling run() without start() raises RuntimeError."""
        runner = Runner(workers=2)

        async def test_async() -> str:
            return await runner.run(lambda: "test")

        with pytest.raises(RuntimeError, match="Runner not started"):
            asyncio.run(test_async())

    def test_exception_handling(self) -> None:
        """Test that exceptions from executor are properly propagated."""

        # Mock function that raises exception
        def failing_function() -> str:
            raise ValueError("Test error")

        runner = Runner(workers=2, executor_type="threading")

        async def test_async() -> str:
            with runner.start() as started_runner:
                return await started_runner.run(failing_function)

        # Verify exception is propagated
        with pytest.raises(ValueError, match="Test error"):
            asyncio.run(test_async())

    def test_different_executor_types(self) -> None:
        """Test that different executor types work correctly."""

        # Test each executor type with a simple function
        def simple_function() -> str:
            return "success"

        executor_types = ["threading", "serial"]  # Skip multiprocessing for simplicity

        for exec_type in executor_types:
            runner = Runner(workers=1, executor_type=exec_type)

            async def _execute_test(_runner: Runner) -> str:
                with _runner.start() as started_runner:
                    return await started_runner.run(simple_function)

            result = asyncio.run(_execute_test(runner))
            assert result == "success"

    def test_context_manager_methods(self) -> None:
        """Test that __enter__ and __exit__ methods exist and work."""
        runner = Runner(workers=2)

        # These methods should exist but not be used (start() is preferred)
        assert hasattr(runner, "__enter__")
        assert hasattr(runner, "__exit__")

        # They should return self and None respectively
        assert runner.__enter__() is runner
        assert runner.__exit__(None, None, None) is None


if __name__ == "__main__":
    pass
# end of file
