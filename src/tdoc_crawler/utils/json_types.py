"""Precise types for JSON-shaped data.

Configuration files, portal responses and stored metadata are JSON documents.
These aliases describe that data exactly so modules never need the vague
``dict[str, Any]`` or ``dict[str, object]`` annotations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

__all__ = ["JSONObject", "JSONScalar", "JSONValue", "coerce_json_value"]

type JSONScalar = str | int | float | bool | None
"""A JSON leaf value."""

type JSONValue = JSONScalar | Sequence[JSONValue] | Mapping[str, JSONValue]
"""Any value that can appear in a JSON document.

``Sequence`` and ``Mapping`` are used instead of ``list``/``dict`` so the
alias is covariant: a ``dict[str, str]`` is a valid :data:`JSONValue`
without an explicit conversion.
"""

type JSONObject = dict[str, JSONValue]
"""A JSON object (mapping of string keys to JSON values)."""


def coerce_json_value(value: object) -> JSONValue:
    """Convert decoded data into the precise JSON value shape.

    Args:
        value: Decoded data of unknown provenance (e.g. the result of
            ``json.loads`` or a parser that returns ``object``).

    Returns:
        The value converted to :data:`JSONValue`.

    Raises:
        TypeError: If the data contains a type that JSON cannot represent.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [coerce_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): coerce_json_value(item) for key, item in value.items()}
    msg = f"Unsupported JSON value type: {type(value).__name__}"
    raise TypeError(msg)
