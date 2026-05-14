"""Pydantic-aware Version subclasses for 3GPP domain types.

Provides ``AgendaItem`` and ``SpecVersion`` — both subclass
``packaging.version.Version`` and implement
``__get_pydantic_core_schema__`` so Oxyde/Pydantic models can store them
as strings while exposing full ``Version`` comparison semantics in Python.
"""

from __future__ import annotations

from packaging.version import Version
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class _VersionField(Version):
    """Base class that makes ``Version`` work as a Pydantic field type.

    Serializes to ``str`` for DB/JSON storage, deserializes from
    ``str | int | Version`` input.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: type, handler: GetCoreSchemaHandler) -> CoreSchema:
        def validate(value: str | int | Version) -> _VersionField:
            if isinstance(value, Version):
                return cls(str(value))
            return cls(str(value).strip())

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )


class AgendaItem(_VersionField):
    """Agenda item number (e.g. ``11.3.2``).

    A ``Version`` subclass — supports ordering, comparison, and
    ``str()`` serialization for DB storage.
    """


class SpecVersion(_VersionField):
    """Three-part specification version (e.g. ``18.1.0``).

    Input is normalized to ``major.minor.patch`` on construction.
    A ``Version`` subclass — supports ordering, comparison, and
    ``str()`` serialization for DB storage.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: type, handler: GetCoreSchemaHandler) -> CoreSchema:
        def validate(value: str | int | Version) -> SpecVersion:
            v = value if isinstance(value, Version) else Version(str(value).strip())
            parts = list(v.release) + [0] * (3 - len(v.release))
            return cls(".".join(str(p) for p in parts[:3]))

        return core_schema.no_info_plain_validator_function(
            validate,
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )


__all__ = ["AgendaItem", "SpecVersion"]
