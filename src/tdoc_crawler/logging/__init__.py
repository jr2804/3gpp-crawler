"""Logging module with RichHandler integration.

Provides a factory function for creating loggers with RichHandler
configured for consistent console output across the application.
"""

import functools
import logging
import sys
from typing import Final

from rich.console import Console
from rich.logging import RichHandler

# Default logging level for all loggers
DEFAULT_LEVEL: Final[int] = logging.WARNING


@functools.cache
def configure_logger() -> None:
    """Configure the root logger with RichHandler.

    This function sets up the RichHandler on the root logger, which all
    child loggers will inherit. It is called on first import of this module.
    """
    _rich_handler: RichHandler = RichHandler(console=get_console(), show_time=True, show_path=False, rich_tracebacks=True, markup=True, tracebacks_width=None)

    # Add RichHandler to root logger (no other handlers)
    logging.root.handlers.clear()
    logging.root.addHandler(_rich_handler)
    # logging.root.addHandler(logging.StreamHandler())
    # logging.root.setLevel(DEFAULT_LEVEL)


@functools.cache
def get_console() -> Console:
    """Get the Rich console instance used by the logging handlers.

    This allows other parts of the application to use the same console
    for consistent output formatting.

    @functools.cache decorator ensures a simple singleton instance of Console is used throughout the application.

    Returns:
        The Rich Console instance configured for logging.
    """
    _console: Console = Console(no_color=not sys.stdout.isatty(), width=120)
    return _console


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


# initialize logger configuration on first import (@functools.cache ensures this runs only once)
configure_logger()
