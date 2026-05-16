from __future__ import annotations

import pytest

from nucleus.application.preview_confirm_safety import (
    build_preview_candidate_payload,
    resolve_preview_workspace_scope,
)


def test_build_preview_candidate_payload_filters_missing_integrity() -> None:
    results = [
        {
            "statement": "Atlas budget is 1200 USD.",
            "citation": {
                "episode_id": "ep_1",
                "source_type": "chat_turn",
                "observed_at": "2026-01-01T10:00:00+00:00",
                "source_hash": "sha256:abc",
            },
        },
        {
            "statement": "Legacy codename is Sparrow.",
            "citation": {
                "episode_id": "ep_2",
                "source_type": "chat_turn",
                "observed_at": "2026-01-01T10:01:00+00:00",
                "source_hash": "sha256:def",
            },
        },
    ]
    integrity = {
        "ep_1": {"state_hash": "sha256:state-1", "source_hash": "sha256:abc"},
    }

    candidates, candidate_integrity, token_integrity = build_preview_candidate_payload(
        results=results,
        integrity=integrity,
    )

    assert [candidate["episode_id"] for candidate in candidates] == ["ep_1"]
    assert candidates[0]["state_hash"] == "sha256:state-1"
    assert candidate_integrity == integrity
    assert token_integrity == {"ep_1": "sha256:state-1"}


def test_resolve_preview_workspace_scope_rejects_profile_global() -> None:
    with pytest.raises(ValueError, match="profile_global scope_mode is not allowed for update_preview"):
        resolve_preview_workspace_scope(
            scope_mode="profile_global",
            operation="update_preview",
        )
