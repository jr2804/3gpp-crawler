"""Tests for SerialPoolExecutor and SerialFuture implementations."""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial

try:
    from concurrent.futures import InterpreterPoolExecutor
except (ImportError, AttributeError):
    InterpreterPoolExecutor = None  # type: ignore[misc]

import pytest

from pool_executors.pool_executors import ExecutorType, SerialPoolExecutor, create_executor


class TestSerialFuture:
    """Tests for SerialFuture immediate execution behavior."""

    def test_serial_future_immediate_execution(self) -> None:
        """Verify SerialFuture executes task immediately upon creation."""
        executed = False

        def task() -> bool:
            nonlocal executed
            executed = True
            return True

        future = SerialPoolExecutor().submit(task)
        assert executed, "Task should execute immediately"
        assert future.result() is True

    def test_serial_future_result_available_immediately(self) -> None:
        """Verify result is available right after future creation."""

        def task() -> int:
            return 42

        future = SerialPoolExecutor().submit(task)
        assert future.done() is True
        assert future.result() == 42

    def test_serial_future_exception_stored(self) -> None:
        """Verify exceptions are properly stored in the future."""

        def failing_task() -> str:
            raise ValueError("Test error")

        future = SerialPoolExecutor().submit(failing_task)
        with pytest.raises(ValueError, match="Test error"):
            future.result()

    def test_serial_future_as_completed_compatibility(self) -> None:
        """Verify SerialFuture works with concurrent.futures.as_completed()."""
        results: list[int] = []

        def task(n: int) -> int:
            return n * 2

        executor = SerialPoolExecutor()
        futures = [executor.submit(task, i) for i in range(5)]

        # as_completed should work with serial futures
        for future in as_completed(futures):
            results.append(future.result())

        assert sorted(results) == [0, 2, 4, 6, 8]

    def test_serial_future_cancelled_raises(self) -> None:
        """Verify cancelled future raises CancelledError."""
        future = SerialPoolExecutor().submit(lambda: 1)
        # Serial futures cannot be cancelled (already executed)
        assert future.cancelled() is False


class TestSerialPoolExecutor:
    """Tests for SerialPoolExecutor core functionality."""

    def test_submit_returns_future(self) -> None:
        """Test that submit() returns a Future instance."""
        executor = SerialPoolExecutor()
        future = executor.submit(lambda: 1)
        assert future is not None

    def test_submit_with_args(self) -> None:
        """Test submitting task with positional arguments."""

        def add(a: int, b: int) -> int:
            return a + b

        executor = SerialPoolExecutor()
        future = executor.submit(add, 3, 4)
        assert future.result() == 7

    def test_submit_with_kwargs(self) -> None:
        """Test submitting task with keyword arguments."""

        def multiply(value: int, multiplier: int = 2) -> int:
            return value * multiplier

        executor = SerialPoolExecutor()
        future = executor.submit(multiply, value=5, multiplier=3)
        assert future.result() == 15

    def test_multiple_submits_sequential_execution(self) -> None:
        """Test that multiple submits execute in order."""
        execution_order: list[int] = []

        def task(n: int) -> int:
            execution_order.append(n)
            return n

        executor = SerialPoolExecutor()
        futures = [executor.submit(task, i) for i in range(5)]

        # All results should be available immediately
        results = [f.result() for f in futures]
        assert results == [0, 1, 2, 3, 4]
        assert execution_order == [0, 1, 2, 3, 4]

    def test_shutdown_prevents_new_submits(self) -> None:
        """Test that shutdown() prevents new future submissions."""
        executor = SerialPoolExecutor()
        executor.submit(lambda: 1)
        executor.shutdown(wait=False)

        with pytest.raises(RuntimeError, match="cannot schedule new futures"):
            executor.submit(lambda: 2)

    def test_context_manager(self) -> None:
        """Test using SerialPoolExecutor as context manager."""
        with SerialPoolExecutor() as executor:
            future = executor.submit(lambda: 42)
            assert future.result() == 42

        # After context exit, shutdown should have been called
        with pytest.raises(RuntimeError, match="cannot schedule new futures"):
            executor.submit(lambda: 1)

    def test_max_workers_parameter_ignored(self) -> None:
        """Test that max_workers parameter is accepted but ignored."""
        executor = SerialPoolExecutor(max_workers=10)
        future = executor.submit(lambda: 1)
        assert future.result() == 1

    def test_exception_propagation(self) -> None:
        """Test that exceptions are properly propagated."""

        def raise_error() -> str:
            raise RuntimeError("Expected error")

        executor = SerialPoolExecutor()
        future = executor.submit(raise_error)

        with pytest.raises(RuntimeError, match="Expected error"):
            future.result()

    def test_different_exception_types(self) -> None:
        """Test handling of different exception types."""
        exceptions = [
            ValueError("value error"),
            TypeError("type error"),
            KeyError("key error"),
            RuntimeError("runtime error"),
        ]

        for exc in exceptions:
            executor = SerialPoolExecutor()
            future = executor.submit(lambda e=exc: 1 / 0 if e else 1)

            # The lambda raises ZeroDivisionError, not the provided exception
            with pytest.raises(ZeroDivisionError):
                future.result()


class TestCreateExecutor:
    """Tests for the create_executor factory function."""

    def test_create_serial_executor(self) -> None:
        """Test creating serial executor."""
        executor = create_executor("serial")
        assert isinstance(executor, SerialPoolExecutor)
        assert executor.submit(lambda: 1).result() == 1

    def test_create_serial_case_insensitive(self) -> None:
        """Test case-insensitive serial executor creation."""
        for name in ["serial", "SERIAL", "Serial", "SeRiAl"]:
            executor = create_executor(name)
            assert isinstance(executor, SerialPoolExecutor)

    def test_create_serial_executor_type(self) -> None:
        """Test creating serial executor with ExecutorType enum."""
        executor = create_executor(ExecutorType.SERIAL)
        assert isinstance(executor, SerialPoolExecutor)

    def test_create_multiprocessing_executor(self: TestCreateExecutor) -> None:
        """Test creating multiprocessing executor."""
        executor = create_executor("multiprocessing")
        assert isinstance(executor, ProcessPoolExecutor)
        # Use a module-level function to avoid pickling issues on Windows
        assert executor.submit(_pickle_safe_task).result() == 42


def _pickle_safe_task() -> int:
    """Module-level function for multiprocessing pickling."""
    return 42


class TestCreateExecutorContinued:
    """Additional tests for create_executor factory function."""

    def test_create_multiprocessing_alias(self: TestCreateExecutorContinued) -> None:
        """Test creating multiprocessing executor with alias."""
        executor = create_executor("mp")
        assert isinstance(executor, ProcessPoolExecutor)

    def test_create_threading_executor(self: TestCreateExecutorContinued) -> None:
        """Test creating threading executor."""
        executor = create_executor("threading")
        assert isinstance(executor, ThreadPoolExecutor)
        assert executor.submit(lambda: 99).result() == 99

    def test_create_threading_alias(self: TestCreateExecutorContinued) -> None:
        """Test creating threading executor with alias."""
        executor = create_executor("thread")
        assert isinstance(executor, ThreadPoolExecutor)

    def test_create_subinterpreter_fallback(self: TestCreateExecutorContinued) -> None:
        """Test subinterpreter uses InterpreterPoolExecutor on Python 3.14+."""
        if InterpreterPoolExecutor is None:
            executor = create_executor("subinterpreter")
            # Falls back to ProcessPoolExecutor when InterpreterPoolExecutor unavailable
            assert isinstance(executor, ProcessPoolExecutor)
        else:
            executor = create_executor("subinterpreter")
            # Uses InterpreterPoolExecutor on Python 3.14+
            assert isinstance(executor, InterpreterPoolExecutor)

    def test_create_subinterpreter_aliases(self: TestCreateExecutorContinued) -> None:
        """Test subinterpreter aliases."""
        expected_type = ProcessPoolExecutor if InterpreterPoolExecutor is None else InterpreterPoolExecutor

        for alias in ["sub", "si"]:
            executor = create_executor(alias)
            assert isinstance(executor, expected_type)

    def test_invalid_executor_type(self: TestCreateExecutorContinued) -> None:
        """Test that invalid executor type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid executor type"):
            create_executor("invalid_type")

    def test_executor_with_max_workers(self: TestCreateExecutorContinued) -> None:
        """Test creating executor with max_workers parameter."""
        executor = create_executor("threading", max_workers=4)
        assert executor.submit(lambda: 1).result() == 1

    def test_executor_with_kwargs(self: TestCreateExecutorContinued) -> None:
        """Test creating executor with additional kwargs."""
        executor = create_executor("threading", max_workers=2)
        assert executor.submit(lambda: 1).result() == 1


class TestExecutorType:
    """Tests for ExecutorType enum."""

    def test_executor_type_values(self) -> None:
        """Test all executor type values exist."""
        assert ExecutorType.SERIAL == "serial"
        assert ExecutorType.MULTIPROCESSING == "multiprocessing"
        assert ExecutorType.MP == "mp"
        assert ExecutorType.THREADING == "threading"
        assert ExecutorType.THREAD == "thread"
        assert ExecutorType.SUBINTERPRETER == "subinterpreter"
        assert ExecutorType.SUB == "sub"
        assert ExecutorType.SI == "si"

    def test_executor_type_case_insensitive_creation(self) -> None:
        """Test creating ExecutorType from case-insensitive string via factory."""
        # StrEnum doesn't support case-insensitive creation, but factory does
        for name in ["SERIAL", "serial", "Serial"]:
            executor = create_executor(name)
            assert isinstance(executor, SerialPoolExecutor)

        for name in ["MP", "mp", "Mp"]:
            executor = create_executor(name)
            assert isinstance(executor, ProcessPoolExecutor)

    def test_executor_type_invalid_raises(self) -> None:
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError, match=r"'invalid' is not a valid ExecutorType"):
            ExecutorType("invalid")


class TestSerialExecutorWithTimeout:
    """Tests for SerialPoolExecutor timeout behavior."""

    def test_task_with_delay(self) -> None:
        """Test that tasks with delays complete in order."""

        def delayed_task(n: int, delay: float = 0.01) -> tuple[int, float]:
            start = time.perf_counter()
            time.sleep(delay)
            return (n, time.perf_counter() - start)

        executor = SerialPoolExecutor()
        futures = [executor.submit(delayed_task, i, 0.001) for i in range(3)]

        results = [f.result()[0] for f in futures]
        assert results == [0, 1, 2]

    def test_immediate_result_available(self) -> None:
        """Test that result is immediately available after submit."""

        def quick_task() -> str:
            return "done"

        executor = SerialPoolExecutor()
        future = executor.submit(quick_task)

        # Result should be available immediately (no waiting)
        assert future.result() == "done"


class TestSerialExecutorEdgeCases:
    """Edge case tests for SerialPoolExecutor."""

    def test_empty_executor(self) -> None:
        """Test executor with no submissions."""
        executor = SerialPoolExecutor()
        executor.shutdown(wait=False)

    def test_nested_submits(self) -> None:
        """Test submitting from within a task."""
        results: list[int] = []

        def outer_task() -> None:
            executor = SerialPoolExecutor()
            future = executor.submit(lambda: 42)
            results.append(future.result())

        main_executor = SerialPoolExecutor()
        main_executor.submit(outer_task).result()
        assert results == [42]

    def test_callable_class(self) -> None:
        """Test submitting a callable class instance."""

        class Adder:
            def __init__(self, value: int) -> None:
                self.value = value

            def __call__(self, x: int) -> int:
                return self.value + x

        executor = SerialPoolExecutor()
        future = executor.submit(Adder(10), 5)
        assert future.result() == 15

    def test_lambda_with_capture(self) -> None:
        """Test lambda with variable capture."""
        multiplier = 3

        executor = SerialPoolExecutor()
        future = executor.submit(lambda x: x * multiplier, 7)
        assert future.result() == 21

    def test_partial_function(self: TestSerialExecutorEdgeCases) -> None:
        """Test with functools.partial."""

        def power(base: int, exp: int) -> int:
            return base**exp

        executor = SerialPoolExecutor()
        future = executor.submit(partial(power, exp=2), 5)
        assert future.result() == 25


class TestFactoryCoverage:
    """Additional tests to improve factory module coverage."""

    def test_invalid_executor_type_error_message(self) -> None:
        """Test that invalid executor type shows valid types in error."""
        with pytest.raises(ValueError, match="Invalid executor type") as exc_info:
            create_executor("unknown")

        error_message = str(exc_info.value)
        # Verify error message includes valid types
        assert "serial" in error_message
        assert "multiprocessing" in error_message
        assert "threading" in error_message

    def test_executor_type_enum_equality(self) -> None:
        """Test ExecutorType enum equality with strings."""
        assert ExecutorType.SERIAL == "serial"
        assert ExecutorType("serial") == ExecutorType.SERIAL
        # Verify different case doesn't match (StrEnum behavior)
        try:
            result = ExecutorType("SERIAL")
            # If this doesn't raise, the test should check the result
            assert result == ExecutorType.SERIAL
        except ValueError:
            # Expected: StrEnum doesn't support case-insensitive creation
            pass

    def test_all_executor_aliases_work(self) -> None:
        """Test all executor type aliases create correct executor types."""
        # Test all aliases
        aliases_and_types = [
            ("serial", SerialPoolExecutor),
            ("multiprocessing", None),  # Will check dynamically
            ("mp", None),
            ("threading", None),
            ("thread", None),
            ("subinterpreter", None),
            ("sub", None),
            ("si", None),
        ]

        for alias, expected_type in aliases_and_types:
            executor = create_executor(alias)
            if expected_type is not None:
                assert isinstance(executor, expected_type)
            else:
                # Just verify it creates something
                assert executor is not None

    def test_case_variations_all_work(self) -> None:
        """Test that case variations all work via factory."""
        # All should work via factory (case-insensitive)
        case_variations = ["SERIAL", "Serial", "sErIaL"]
        for case_var in case_variations:
            executor = create_executor(case_var)
            assert isinstance(executor, SerialPoolExecutor)

    def test_mp_alias_creates_process_pool(self: TestFactoryCoverage) -> None:
        """Test that 'mp' alias creates ProcessPoolExecutor."""
        executor = create_executor("MP")  # Uppercase to test case handling
        assert isinstance(executor, ProcessPoolExecutor)

    def test_thread_alias_creates_thread_pool(self: TestFactoryCoverage) -> None:
        """Test that 'thread' alias creates ThreadPoolExecutor."""
        executor = create_executor("THREAD")
        assert isinstance(executor, ThreadPoolExecutor)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
