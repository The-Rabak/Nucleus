from __future__ import annotations

import re

_SCOPE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_scope_identifier(*, name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    if not _SCOPE_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{name} must match pattern {_SCOPE_ID_PATTERN.pattern!r} and cannot contain path separators."
        )
    return value

