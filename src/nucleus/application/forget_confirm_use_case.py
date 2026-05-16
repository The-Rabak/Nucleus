from __future__ import annotations

from datetime import UTC, datetime

from nucleus.application.ports import EpisodeRepository
from nucleus.domain.constants import MutationOperation, PreviewOperation
from nucleus.domain.models import ForgetConfirmResult
from nucleus.domain.preview_token import PreviewTokenClaims, parse_preview_token
from nucleus.domain.scoping import ScopeDecision, resolve_scope_mode


class ForgetConfirmUseCase:
    """Applies forget confirmations after preview-token safety checks."""

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
        """Marks selected preview candidates as forgotten."""
        claims = self._validated_claims(
            preview_token=preview_token,
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        selected = self._validated_selection(
            selected_episode_ids=selected_episode_ids,
            allowed_episode_ids=set(claims.candidate_integrity),
        )
        self._validate_token_and_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            selected_episode_ids=selected,
            claims=claims,
        )
        return self._confirmation_result(
            profile_id=profile_id,
            workspace_id=workspace_id,
            selected_episode_ids=selected,
            claims=claims,
        )

    def _confirmation_result(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        selected_episode_ids: list[str],
        claims: PreviewTokenClaims,
    ) -> ForgetConfirmResult:
        audit = self._apply_confirmation(
            profile_id=profile_id,
            workspace_id=workspace_id,
            selected_episode_ids=selected_episode_ids,
            claims=claims,
        )
        scope = resolve_scope_mode(scope_mode=claims.scope_mode)
        return self._result(scope=scope, selected_episode_ids=selected_episode_ids, audit=audit)

    @staticmethod
    def _validated_claims(
        *,
        preview_token: str,
        profile_id: str,
        workspace_id: str,
    ) -> PreviewTokenClaims:
        claims = parse_preview_token(preview_token)
        if claims.operation != PreviewOperation.FORGET.value:
            raise ValueError("preview_token operation mismatch.")
        if claims.profile_id != profile_id or claims.workspace_id != workspace_id:
            raise ValueError("preview_token scope mismatch.")
        return claims

    @staticmethod
    def _validated_selection(
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

    def _validate_token_and_integrity(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        selected_episode_ids: list[str],
        claims: PreviewTokenClaims,
    ) -> None:
        self._ensure_active_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            token_id=claims.token_id,
            scope_mode=claims.scope_mode,
        )
        self._ensure_current_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            selected_episode_ids=selected_episode_ids,
            claims=claims,
        )

    def _ensure_active_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        token_id: str,
        scope_mode: str,
    ) -> None:
        if self._episode_store.is_preview_token_active(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation=PreviewOperation.FORGET.value,
            scope_mode=scope_mode,
            token_id=token_id,
            now=datetime.now(UTC),
        ):
            return
        raise ValueError("preview_token stale; request a fresh preview.")

    def _ensure_current_integrity(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        selected_episode_ids: list[str],
        claims: PreviewTokenClaims,
    ) -> None:
        current_integrity = self._episode_store.candidate_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=selected_episode_ids,
            scope_mode=claims.scope_mode,
        )
        for episode_id in selected_episode_ids:
            current_state_hash = current_integrity.get(episode_id, {}).get("state_hash")
            if current_state_hash != claims.candidate_integrity[episode_id]:
                raise ValueError("preview_token mismatch with current candidate state.")

    def _apply_confirmation(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        selected_episode_ids: list[str],
        claims: PreviewTokenClaims,
    ) -> dict[str, object]:
        audit = self._episode_store.mark_forgotten(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=selected_episode_ids,
            token_id=claims.token_id,
            scope_mode=claims.scope_mode,
        )
        self._episode_store.invalidate_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation=PreviewOperation.FORGET.value,
            scope_mode=claims.scope_mode,
            token_id=claims.token_id,
        )
        return audit

    @staticmethod
    def _result(
        *,
        scope: ScopeDecision,
        selected_episode_ids: list[str],
        audit: dict[str, object],
    ) -> ForgetConfirmResult:
        return ForgetConfirmResult(
            operation=MutationOperation.FORGET_CONFIRM.value,
            effective_scope=scope.effective_scope,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            forgotten_episode_ids=selected_episode_ids,
            audit=audit,
        )
