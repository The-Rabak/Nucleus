from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from nucleus.application.ports import EpisodeRepository
from nucleus.domain.constants import ScopeMode
from nucleus.domain.preview_token import PreviewTokenClaims, parse_preview_token
from nucleus.domain.scoping import ScopeDecision, resolve_scope_mode


def resolve_preview_workspace_scope(*, scope_mode: str | None, operation: str) -> ScopeDecision:
    scope = resolve_scope_mode(scope_mode=scope_mode)
    if scope.scope_widened:
        raise ValueError(f"{ScopeMode.PROFILE_GLOBAL.value} scope_mode is not allowed for {operation}.")
    return scope


def build_preview_candidate_payload(
    *,
    results: list[dict[str, object]],
    integrity: dict[str, dict[str, str]],
) -> tuple[list[dict[str, object]], dict[str, dict[str, str]], dict[str, str]]:
    candidates: list[dict[str, object]] = []
    candidate_integrity: dict[str, dict[str, str]] = {}
    token_integrity: dict[str, str] = {}
    for result in results:
        citation = cast(dict[str, object], result["citation"])
        episode_id = str(citation["episode_id"])
        integrity_snapshot = integrity.get(episode_id)
        if integrity_snapshot is None:
            continue
        candidate_integrity[episode_id] = integrity_snapshot
        token_integrity[episode_id] = integrity_snapshot["state_hash"]
        candidates.append(
            {
                "episode_id": episode_id,
                "statement": result["statement"],
                "source_type": citation["source_type"],
                "observed_at": citation["observed_at"],
                "source_hash": citation["source_hash"],
                "state_hash": integrity_snapshot["state_hash"],
            }
        )
    return candidates, candidate_integrity, token_integrity


def validated_preview_claims(
    *,
    preview_token: str,
    profile_id: str,
    workspace_id: str,
    episode_store: EpisodeRepository,
    expected_operation: str,
) -> PreviewTokenClaims:
    signing_key = episode_store.preview_token_signing_key(
        profile_id=profile_id,
        workspace_id=workspace_id,
    )
    claims = parse_preview_token(preview_token, signing_key=signing_key)
    if claims.operation != expected_operation:
        raise ValueError("preview_token operation mismatch.")
    if claims.profile_id != profile_id or claims.workspace_id != workspace_id:
        raise ValueError("preview_token scope mismatch.")
    return claims


def validated_preview_selection(
    *,
    selected_episode_ids: list[str],
    allowed_episode_ids: set[str],
) -> list[str]:
    selected = sorted(set(selected_episode_ids))
    if not selected:
        raise ValueError("selected_episode_ids must include at least one candidate.")
    if not set(selected).issubset(allowed_episode_ids):
        raise ValueError("selected_episode_ids mismatch preview candidates.")
    return selected


def ensure_active_preview_token(
    *,
    episode_store: EpisodeRepository,
    profile_id: str,
    workspace_id: str,
    operation: str,
    scope_mode: str,
    token_id: str,
    claims_digest: str,
) -> None:
    if episode_store.is_preview_token_active(
        profile_id=profile_id,
        workspace_id=workspace_id,
        operation=operation,
        scope_mode=scope_mode,
        token_id=token_id,
        claims_digest=claims_digest,
        now=datetime.now(UTC),
    ):
        return
    raise ValueError("preview_token stale; request a fresh preview.")


def ensure_current_preview_integrity(
    *,
    episode_store: EpisodeRepository,
    profile_id: str,
    workspace_id: str,
    selected_episode_ids: list[str],
    claims: PreviewTokenClaims,
) -> None:
    current_integrity = episode_store.candidate_integrity(
        profile_id=profile_id,
        workspace_id=workspace_id,
        episode_ids=selected_episode_ids,
        scope_mode=claims.scope_mode,
    )
    for episode_id in selected_episode_ids:
        current_state_hash = current_integrity.get(episode_id, {}).get("state_hash")
        if current_state_hash != claims.candidate_integrity[episode_id]:
            raise ValueError("preview_token mismatch with current candidate state.")
