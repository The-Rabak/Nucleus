from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nucleus.domain.preview_token import PreviewTokenClaims, issue_preview_token, parse_preview_token

_SIGNING_KEY = "unit-test-preview-token-signing-key"


def test_preview_token_round_trip_preserves_claims() -> None:
    now = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    token, claims = issue_preview_token(
        operation="update",
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        scope_mode="workspace_local",
        candidate_integrity={"ep_1": "sig_1"},
        ttl_seconds=300,
        signing_key=_SIGNING_KEY,
        now=now,
    )

    parsed = parse_preview_token(token, signing_key=_SIGNING_KEY, now=now + timedelta(seconds=1))

    assert isinstance(claims, PreviewTokenClaims)
    assert parsed.token_id == claims.token_id
    assert parsed.operation == "update"
    assert parsed.profile_id == "profile-alpha"
    assert parsed.workspace_id == "workspace-core"
    assert parsed.scope_mode == "workspace_local"
    assert parsed.candidate_integrity == {"ep_1": "sig_1"}
    assert parsed.expires_at == (now + timedelta(seconds=300)).isoformat()


def test_preview_token_rejects_expired_tokens() -> None:
    now = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    token, _ = issue_preview_token(
        operation="forget",
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        scope_mode="workspace_local",
        candidate_integrity={"ep_2": "sig_2"},
        ttl_seconds=30,
        signing_key=_SIGNING_KEY,
        now=now,
    )

    with pytest.raises(ValueError, match="expired"):
        parse_preview_token(token, signing_key=_SIGNING_KEY, now=now + timedelta(seconds=31))


def test_preview_token_rejects_tampered_payload() -> None:
    now = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    token, _ = issue_preview_token(
        operation="update",
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        scope_mode="workspace_local",
        candidate_integrity={"ep_3": "sig_3"},
        ttl_seconds=120,
        signing_key=_SIGNING_KEY,
        now=now,
    )

    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.deadbeef"

    with pytest.raises(ValueError, match="signature mismatch"):
        parse_preview_token(tampered, signing_key=_SIGNING_KEY, now=now)
