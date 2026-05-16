from __future__ import annotations

import hashlib
import re

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class CheckpointIdempotency:
    @staticmethod
    def normalize(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("idempotency_key must be a string.")
        if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
            raise ValueError(
                "idempotency_key must match pattern "
                f"{_IDEMPOTENCY_KEY_PATTERN.pattern!r}."
            )
        return value

    @classmethod
    def checkpoint_id(
        cls,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
        trigger: str,
        idempotency_key: str,
    ) -> str:
        normalized_key = cls.normalize(idempotency_key)
        digest = hashlib.sha256(
            f"{profile_id}:{workspace_id}:{session_id}:{trigger}:{normalized_key}".encode("utf-8")
        ).hexdigest()[:16]
        return f"cp_{digest}"
