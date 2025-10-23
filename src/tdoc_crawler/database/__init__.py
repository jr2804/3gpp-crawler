"""Database facade exports."""

from .connection import TDocDatabase
from .errors import DatabaseError

__all__ = ["DatabaseError", "TDocDatabase"]
