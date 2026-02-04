# pool-executors

Lightweight executor pool extensions for Python 3.13+, providing a unified interface for different execution strategies including serial (non-parallel) execution.

## Features

- **SerialPoolExecutor**: Execute tasks sequentially in the main thread (useful for debugging or when parallelism is not needed)
- **Unified factory**: Create any executor type with a consistent interface
- **Type-safe**: Full type hints for mypy strict mode
- **Case-insensitive**: Accept executor types in any case (e.g., "serial", "SERIAL", "Serial")
- **Alias support**: Use short aliases like "mp" for "multiprocessing"

## Installation

```bash
pip install pool-executors
```

## Usage Examples

### Using SerialPoolExecutor Directly

```python
from pool_executors import SerialPoolExecutor

def task(x: int) -> int:
    return x * 2

with SerialPoolExecutor() as executor:
    futures = [executor.submit(task, i) for i in range(5)]
    results = [f.result() for f in futures]
    print(results)  # [0, 2, 4, 6, 8]
```

### Using the Factory with Case-Insensitive Types

```python
from pool_executors import create_executor, ExecutorType

# All of these are equivalent:
executor = create_executor("serial")
executor = create_executor("SERIAL")
executor = create_executor(ExecutorType.SERIAL)

# Use aliases for convenience:
executor = create_executor("mp", max_workers=4)  # ProcessPoolExecutor
executor = create_executor("thread", max_workers=4)  # ThreadPoolExecutor
```

### Factory with Keyword Arguments

```python
from pool_executors import create_executor

# All kwargs are forwarded to the underlying executor
executor = create_executor(
    "multiprocessing",
    max_workers=4,
    initializer=setup_fn,
    initargs=(arg1, arg2)
)
```

### Executor Type Reference

| Type | Aliases | Description |
|------|---------|-------------|
| `serial` | - | Sequential execution in main thread (SerialPoolExecutor) |
| `multiprocessing` | `mp` | True parallelism with separate processes (ProcessPoolExecutor) |
| `threading` | `thread` | Concurrent execution with threads (ThreadPoolExecutor) |
| `subinterpreter` | `sub`, `si` | Subinterpreter-based parallelism (Python 3.14+, fallback to multiprocessing) |

## Design Rationale

This package was created to:

1. **Provide serial execution**: Sometimes you need to disable parallelism for debugging or when overhead outweighs benefits
1. **Unify executor creation**: Single factory function for all executor types with consistent interface
1. **Enable future extraction**: Designed as standalone package for easy repository separation

## Subinterpreter Support

### Why Subinterpreters?

Python's Global Interpreter Lock (GIL) and thread-safety issues in many C extensions limit the effectiveness of standard threading. Subinterpreters provide an alternative approach:

- **Thread Safety**: Each subinterpreter has its own GIL, providing true isolation between tasks
- **Performance**: Similar to real threading without the thread-safety concerns of shared-memory threading
- **Encapsulation**: Each subinterpreter runs in complete isolation with its own interpreter state

### Subinterpreters vs Other Execution Strategies

| Strategy | Pros | Cons |
|----------|------|------|
| **Serial** | No overhead, deterministic, easy debugging | No parallelism |
| **Threading** | Low overhead, shared memory | GIL contention, thread-safety issues in many libraries |
| **Multiprocessing** | True parallelism, no GIL | High inter-process communication overhead, especially on Windows |
| **Subinterpreter** | Thread-safety isolation, good performance | Python 3.14+ required, still maturing |

### Future Outlook

As Python 3.14+ matures and more libraries become subinterpreter-safe, this approach will provide a clean path toward concurrent execution without the overhead of multiprocessing. Until then, using well-encapsulated subinterpreters offers a good balance between thread-safety and performance characteristics similar to real multi-threading.

### Fallback Behavior

When `InterpreterPoolExecutor` is not available (Python < 3.14), the factory automatically falls back to `ProcessPoolExecutor` with a warning log message.

## Requirements

- Python 3.13 or higher
- Python 3.14+ recommended for subinterpreter support
- No external dependencies (stdlib only)

## Runner: Async Integration Adapter

The `Runner` class provides an async-compatible interface for `pool_executors`, enabling seamless integration with asyncio-based applications. It mimics the `aiointerpreters.Runner` API while leveraging the underlying `pool_executors` for task execution.

### Key Features

- **Async/Await Support**: Run synchronous functions asynchronously using `await runner.run(func, *args, **kwargs)`
- **Context Manager**: Manage executor lifecycle with `with runner.start():`
- **Flexible Executor Types**: Use any `pool_executors` backend (multiprocessing, threading, subinterpreter, or serial)
- **Thread-Safe**: Designed for use in async applications with proper event loop handling

### Usage Examples

#### Basic Async Integration

```python
from pool_executors import Runner
import asyncio

def cpu_intensive_task(x: int) -> int:
    return x * x

async def main():
    # Create runner with 4 workers using multiprocessing
    runner = Runner(workers=4, executor_type="multiprocessing")

    # Use context manager to start executor
    async with runner.start():
        # Run tasks asynchronously
        results = await asyncio.gather(
            runner.run(cpu_intensive_task, 2),
            runner.run(cpu_intensive_task, 3),
            runner.run(cpu_intensive_task, 4)
        )
        print(results)  # [4, 9, 16]

asyncio.run(main())
```

#### Using Different Executor Types

```python
from pool_executors import Runner

async def io_bound_task(url: str) -> str:
    import requests
    return requests.get(url).text[:100]  # Return first 100 chars

async def main():
    # Use threading for I/O-bound tasks
    runner = Runner(workers=8, executor_type="threading")

    async with runner.start():
        result = await runner.run(io_bound_task, "https://example.com")
        print(result)

asyncio.run(main())
```

#### Integration with Existing Async Code

```python
from pool_executors import Runner
import asyncio

def process_data(data: list) -> list:
    return [x * 2 for x in data]

async def fetch_data() -> list:
    # Simulate async data fetching
    await asyncio.sleep(0.1)
    return [1, 2, 3, 4, 5]

async def main():
    runner = Runner(workers=2, executor_type="subinterpreter")

    async with runner.start():
        # Fetch data asynchronously
        data = await fetch_data()

        # Process data in executor
        processed = await runner.run(process_data, data)
        print(processed)  # [2, 4, 6, 8, 10]

asyncio.run(main())
```

### Runner API Reference

| Method/Property | Description |
|-----------------|-------------|
| `Runner(workers=4, executor_type="multiprocessing")` | Initialize runner with specified workers and executor type |
| `runner.start()` | Returns context manager for executor lifecycle |
| `await runner.run(func, *args, **kwargs)` | Run function in executor and return awaitable result |
| `runner.executor_type` | Get the executor type (read-only) |
| `runner.workers` | Get the number of workers (read-only) |

### When to Use Runner

Use the `Runner` class when:

1. **Integrating with async applications**: When you need to run synchronous code from async contexts
1. **Migrating from aiointerpreters**: For compatibility with code written for `aiointerpreters.Runner`
1. **Leveraging async/await**: When you want to use async/await syntax with pool executors
1. **Managing complex workflows**: For applications that mix async I/O with CPU-bound tasks

### Advanced Usage

#### Error Handling

```python
from pool_executors import Runner
import asyncio

def might_fail(x: int) -> int:
    if x < 0:
        raise ValueError("Negative values not allowed")
    return x * x

async def main():
    runner = Runner(workers=2)

    async with runner.start():
        try:
            result = await runner.run(might_fail, -5)
        except ValueError as e:
            print(f"Error: {e}")  # Error: Negative values not allowed

asyncio.run(main())
```

#### Custom Initialization

```python
from pool_executors import Runner
import asyncio

def init_db_connection():
    # Initialize database connection
    pass

def query_database(user_id: int) -> dict:
    # Use initialized connection
    return {"id": user_id, "name": "Test User"}

async def main():
    # Initialize with custom setup
    runner = Runner(workers=4, executor_type="multiprocessing")

    async with runner.start():
        # Run with initialized state
        result = await runner.run(query_database, 42)
        print(result)  # {"id": 42, "name": "Test User"}

asyncio.run(main())
```

## License

MIT License - see LICENSE file for details.
