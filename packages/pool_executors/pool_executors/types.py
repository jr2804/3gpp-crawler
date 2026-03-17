"""Executor type enumeration with aliases."""

from enum import StrEnum


class ExecutorType(StrEnum):
    """Executor types for pool creation.

    Supports multiple aliases for convenience:
    - MULTIPROCESSING / MP: Process-based parallelism
    - THREADING / THREAD: Thread-based concurrency
    - SUBINTERPRETER / SUB / SI: Subinterpreter-based parallelism (Python 3.14+)
    - SERIAL: Sequential execution in main thread
    """

    MULTIPROCESSING = "multiprocessing"
    MP = "mp"
    THREADING = "threading"
    THREAD = "thread"
    SUBINTERPRETER = "subinterpreter"
    SUB = "sub"
    SI = "si"
    SERIAL = "serial"
