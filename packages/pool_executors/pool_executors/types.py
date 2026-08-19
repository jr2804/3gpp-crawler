"""Executor type enumeration."""

from __future__ import annotations

from enum import StrEnum


class ExecutorType(StrEnum):
    """Executor types for pool creation.

    Canonical values only. Short aliases (e.g. "mp", "thread", "sub", "si")
    are accepted by ``create_executor`` and resolved to the canonical form
    via ``ExecutorType._missing_``.
    """

    MULTIPROCESSING = "multiprocessing"
    THREADING = "threading"
    SUBINTERPRETER = "subinterpreter"
    SERIAL = "serial"

    @classmethod
    def _missing_(cls, value: object) -> ExecutorType:
        """Resolve aliases to canonical values during ``ExecutorType(value)``.

        Returns the canonical ExecutorType for known aliases (case-insensitive),
        or raises ValueError for unknown values.
        """
        if not isinstance(value, str):
            msg = f"{value!r} is not a valid ExecutorType"
            raise ValueError(msg)
        normalized = value.strip().lower()
        # canonical values (lowered) are also valid aliases
        for member in cls:
            if member.value == normalized:
                return member
        if normalized in _ALIASES:
            return cls(_ALIASES[normalized])
        canonical = sorted(member.value for member in cls)
        msg = f"{value!r} is not a valid ExecutorType. Valid values: {canonical}"
        raise ValueError(msg)


_ALIASES: dict[str, ExecutorType] = {
    "mp": ExecutorType.MULTIPROCESSING,
    "thread": ExecutorType.THREADING,
    "sub": ExecutorType.SUBINTERPRETER,
    "si": ExecutorType.SUBINTERPRETER,
}
