"""Logging module with RichHandler integration.

Provides a factory function for creating loggers with RichHandler
configured for consistent console output across the application.
"""

import functools
import logging
from typing import Final

from rich.console import Console
from rich.logging import RichHandler

# Default logging level for all loggers
DEFAULT_LEVEL: Final[int] = logging.WARNING

# Configure the root logger with RichHandler on first import
_console: Final[Console] = Console()
_rich_handler: RichHandler = RichHandler(
    console=_console,
    show_time=True,
    show_path=False,
    rich_tracebacks=True,
    markup=False,
    tracebacks_width=None,
)

# Add RichHandler to root logger (no other handlers)
logging.root.handlers.clear()
logging.root.addHandler(_rich_handler)
logging.root.setLevel(DEFAULT_LEVEL)


@functools.cache
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with RichHandler configured.

    This factory function returns cached logger instances for consistent
    logging across the application. The first call sets up the
    RichHandler on the root logger, which all child loggers inherit.

    Args:
        name: The logger name, typically __name__ of the calling module.

    Returns:
        A configured logger instance.

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting operation")
        >>> logger.debug("Detailed diagnostic information")
    """
    return logging.getLogger(name)


def set_verbosity(level: int | str) -> None:
    """Set the logging level for all loggers.

    This updates the root logger level, which affects all child loggers
    created via get_logger().

    Args:
        level: The logging level (e.g., logging.DEBUG, logging.INFO, etc.)
                   Accepts integer values (0-50), logging constants, or string names of levels.

    Examples:
        >>> set_verbosity(logging.DEBUG)
        >>> set_verbosity(10)  # DEBUG level
    """
    if isinstance(level, str):
        level = level.upper()
        if level_int := logging._nameToLevel.get(level):
            level = level_int
        elif level.isnumeric():
            level = int(level)
        else:
            raise ValueError(f"Invalid logging level name: {level}")

    logging.root.setLevel(level)
