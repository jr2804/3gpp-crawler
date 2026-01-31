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

## License

MIT License - see LICENSE file for details.
