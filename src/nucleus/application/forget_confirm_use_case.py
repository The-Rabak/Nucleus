from __future__ import annotations

from datetime import UTC, datetime

from nucleus.application.ports import EpisodeRepository
from nucleus.domain.models import ForgetConfirmResult
from nucleus.domain.preview_token import parse_preview_token
from nucleus.domain.scoping import resolve_scope_mode


class ForgetConfirmUseCase:
    def __init__(self, *, episode_store: EpisodeRepository) -> None:
        self._episode_store = episode_store

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        preview_token: str,
        selected_episode_ids: list[str],
    ) -> ForgetConfirmResult:
        claims = parse_preview_token(preview_token)
        if claims.operation != "forget":
            raise ValueError("preview_token operation mismatch.")
        if claims.profile_id != profile_id or claims.workspace_id != workspace_id:
            raise ValueError("preview_token scope mismatch.")

        selected = sorted(set(selected_episode_ids))
        if not selected:
            raise ValueError("selected_episode_ids must include at least one candidate.")

        allowed = set(claims.candidate_integrity)
        if not set(selected).issubset(allowed):
            raise ValueError("selected_episode_ids mismatch preview candidates.")

        now = datetime.now(UTC)
        if not self._episode_store.is_preview_token_active(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation="forget",
            scope_mode=claims.scope_mode,
            token_id=claims.token_id,
            now=now,
        ):
            raise ValueError("preview_token stale; request a fresh preview.")

        current_integrity = self._episode_store.candidate_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=selected,
            scope_mode=claims.scope_mode,
        )
        for episode_id in selected:
            current_state_hash = current_integrity.get(episode_id, {}).get("state_hash")
            if current_state_hash != claims.candidate_integrity[episode_id]:
                raise ValueError("preview_token mismatch with current candidate state.")

        audit = self._episode_store.mark_forgotten(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=selected,
            token_id=claims.token_id,
            scope_mode=claims.scope_mode,
        )
        self._episode_store.invalidate_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation="forget",
            scope_mode=claims.scope_mode,
            token_id=claims.token_id,
        )

        scope = resolve_scope_mode(scope_mode=claims.scope_mode)
        return ForgetConfirmResult(
            operation="forget_confirm",
            effective_scope=scope.effective_scope,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            forgotten_episode_ids=selected,
            audit=audit,
        )
