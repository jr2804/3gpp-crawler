"""pg0 Manager for LightRAG PostgreSQL storage.

This module manages pg0 lifecycle for PostgreSQL-backed LightRAG storage.
pg0 is a zero-config embedded PostgreSQL with pgvector extension.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

try:
    from pg0 import Pg0 as _Pg0
except ImportError:
    _Pg0 = None

logger = logging.getLogger(__name__)


class Pg0Manager:
    """Manages pg0 PostgreSQL instance for LightRAG storage.

    Args:
        instance_name: Name of the pg0 instance (stored in ~/.pg0/instances/<name>/)
        port: PostgreSQL port (default: 15432)
        database: Database name (default: tdoc)

    Example:
        >>> manager = Pg0Manager()
        >>> with manager.running() as uri:
        ...     print(f"PostgreSQL running at {uri}")
    """

    def __init__(
        self,
        instance_name: str = "3gpp-crawler",
        port: int = 15432,
        database: str = "tdoc",
    ) -> None:
        self.instance_name = instance_name
        self.port = port
        self.database = database
        self._pg = None
        self._started = False

    def start(self) -> str:
        """Start pg0 and return connection URI.

        Returns:
            PostgreSQL connection URI string.

        Raises:
            Pg0Error: If pg0 fails to start or pg0-embedded is not installed.
        """
        if _Pg0 is None:
            raise Pg0Error("pg0-embedded not installed")

        if self._started:
            return self.uri

        self._pg = _Pg0(
            name=self.instance_name,
            port=self.port,
            database=self.database,
        )

        try:
            self._pg.start()
            self._pg.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info(
                "pg0 started on port %d with pgvector",
                self.port,
            )
            self._started = True
        except Exception as e:
            raise Pg0Error(f"Failed to start pg0: {e}") from e

        return self.uri

    def stop(self) -> None:
        """Stop pg0 instance."""
        if self._pg and self._started:
            self._pg.stop()
            logger.info("pg0 stopped")
            self._started = False

    def is_running(self) -> bool:
        """Check if pg0 is currently running."""
        return self._started

    @property
    def uri(self) -> str:
        """Return PostgreSQL connection URI."""
        return f"postgresql://postgres:postgres@localhost:{self.port}/{self.database}"

    @contextmanager
    def running(self) -> Generator[str]:
        """Context manager for pg0 lifecycle.

        Yields:
            PostgreSQL connection URI.

        Example:
            >>> manager = Pg0Manager()
            >>> with manager.running() as uri:
            ...     # use PostgreSQL
        """
        try:
            yield self.start()
        finally:
            self.stop()


class Pg0Error(Exception):
    """Raised when pg0 fails to start or connect."""
