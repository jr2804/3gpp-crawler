"""Normalization helpers for spec identifiers."""

import re

_SPEC_PATTERN = re.compile(r"^(?P<prefix>[A-Z]+)?(?P<body>\d{2,}(?:\.\d{3})?)$")


def normalize_spec_number(value: str) -> str:
    """Normalize spec numbers to dotted canonical format.

    Args:
        value: Spec number in dotted or undotted form.

    Returns:
        Normalized dotted spec number (e.g., "26.132").

    Raises:
        ValueError: When the spec number is not in a supported format.
    """
    raw = value.strip().upper().replace(" ", "")
    if not raw:
        raise ValueError("Spec number is required")

    match = _SPEC_PATTERN.match(raw)
    if not match:
        raise ValueError(f"Unsupported spec number format: {value}")

    body = match.group("body")
    if "." in body:
        left, right = body.split(".", maxsplit=1)
        if not (left.isdigit() and right.isdigit()):
            raise ValueError(f"Unsupported spec number format: {value}")
        if len(right) != 3:
            raise ValueError(f"Unsupported spec number format: {value}")
        return f"{int(left)}.{right.zfill(3)}"

    if not body.isdigit() or len(body) < 4:
        raise ValueError(f"Unsupported spec number format: {value}")

    left = body[:-3]
    right = body[-3:]
    return f"{int(left)}.{right}"
