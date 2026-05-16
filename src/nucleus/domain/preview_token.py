from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import base64
import hashlib
import json
import uuid

from nucleus.domain.constants import VALID_PREVIEW_OPERATIONS

_TOKEN_PREFIX = "npt1"


@dataclass(frozen=True, slots=True)
class PreviewTokenClaims:
    token_id: str
    operation: str
    profile_id: str
    workspace_id: str
    scope_mode: str
    issued_at: str
    expires_at: str
    candidate_integrity: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "token_id": self.token_id,
            "operation": self.operation,
            "profile_id": self.profile_id,
            "workspace_id": self.workspace_id,
            "scope_mode": self.scope_mode,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "candidate_integrity": dict(sorted(self.candidate_integrity.items())),
        }


def issue_preview_token(
    *,
    operation: str,
    profile_id: str,
    workspace_id: str,
    scope_mode: str,
    candidate_integrity: dict[str, str],
    ttl_seconds: int,
    now: datetime | None = None,
) -> tuple[str, PreviewTokenClaims]:
    _validate_token_request(operation=operation, ttl_seconds=ttl_seconds)
    issued_at_dt = _coerce_utc(now or datetime.now(UTC))
    expires_at_dt = issued_at_dt + timedelta(seconds=ttl_seconds)
    claims = _claims(
        operation=operation,
        profile_id=profile_id,
        workspace_id=workspace_id,
        scope_mode=scope_mode,
        issued_at=issued_at_dt,
        expires_at=expires_at_dt,
        candidate_integrity=candidate_integrity,
    )
    return _token(claims), claims


def parse_preview_token(token: str, *, now: datetime | None = None) -> PreviewTokenClaims:
    encoded_payload = _validated_encoded_payload(token)
    claims = _claims_from_payload(_decode_payload(encoded_payload))
    _validate_claims(claims, now=now)
    return claims


def _decode_payload(encoded_payload: str) -> dict[str, object]:
    padded_payload = encoded_payload + "=" * ((4 - len(encoded_payload) % 4) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded_payload.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("preview_token payload is invalid.") from exc
    if not isinstance(payload, dict):
        raise ValueError("preview_token payload is invalid.")
    return payload


def _checksum(encoded_payload: str) -> str:
    return hashlib.sha256(f"{_TOKEN_PREFIX}.{encoded_payload}".encode("utf-8")).hexdigest()[:16]


def _validate_token_request(*, operation: str, ttl_seconds: int) -> None:
    if operation not in VALID_PREVIEW_OPERATIONS:
        raise ValueError(
            f"operation must be one of: {', '.join(sorted(VALID_PREVIEW_OPERATIONS))}."
        )
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be > 0.")


def _coerce_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp


def _claims(
    *,
    operation: str,
    profile_id: str,
    workspace_id: str,
    scope_mode: str,
    issued_at: datetime,
    expires_at: datetime,
    candidate_integrity: dict[str, str],
) -> PreviewTokenClaims:
    return PreviewTokenClaims(
        token_id=f"ptk_{uuid.uuid4().hex[:12]}",
        operation=operation,
        profile_id=profile_id,
        workspace_id=workspace_id,
        scope_mode=scope_mode,
        issued_at=issued_at.isoformat(),
        expires_at=expires_at.isoformat(),
        candidate_integrity=dict(sorted(candidate_integrity.items())),
    )


def _token(claims: PreviewTokenClaims) -> str:
    payload = json.dumps(claims.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    return f"{_TOKEN_PREFIX}.{encoded_payload}.{_checksum(encoded_payload)}"


def _validated_encoded_payload(token: str) -> str:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
        raise ValueError("preview_token format is invalid.")
    encoded_payload, checksum = parts[1], parts[2]
    if checksum != _checksum(encoded_payload):
        raise ValueError("preview_token checksum mismatch.")
    return encoded_payload


def _claims_from_payload(payload: dict[str, object]) -> PreviewTokenClaims:
    return PreviewTokenClaims(
        token_id=str(payload["token_id"]),
        operation=str(payload["operation"]),
        profile_id=str(payload["profile_id"]),
        workspace_id=str(payload["workspace_id"]),
        scope_mode=str(payload["scope_mode"]),
        issued_at=str(payload["issued_at"]),
        expires_at=str(payload["expires_at"]),
        candidate_integrity={
            str(key): str(value)
            for key, value in dict(payload.get("candidate_integrity", {})).items()
        },
    )


def _validate_claims(claims: PreviewTokenClaims, *, now: datetime | None) -> None:
    if claims.operation not in VALID_PREVIEW_OPERATIONS:
        raise ValueError("preview_token operation mismatch.")
    expires_at = _coerce_utc(datetime.fromisoformat(claims.expires_at))
    now_dt = _coerce_utc(now or datetime.now(UTC))
    if now_dt > expires_at:
        raise ValueError("preview_token expired.")
