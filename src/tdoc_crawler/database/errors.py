"""Database errors and exceptions."""

from __future__ import annotations


class DatabaseError(RuntimeError):
    """Raised when a database constraint or execution fails."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        message = f"{code}:{detail}" if detail else code
        super().__init__(message)

    @classmethod
    def connection_not_open(cls) -> DatabaseError:
        return cls("connection-not-open")
