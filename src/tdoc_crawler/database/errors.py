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

    @classmethod
    def crawl_log_persist_failed(cls) -> DatabaseError:
        return cls("crawl-log-persist-failed")

    @classmethod
    def parse_failure(cls, entity: str, detail: str) -> DatabaseError:
        return cls(f"{entity}-parse-failed", detail=detail)

    @classmethod
    def missing_datetime(cls) -> DatabaseError:
        return cls("missing-required-datetime")
