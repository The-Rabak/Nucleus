from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass

from nucleus.application.ports import EpisodeRepository
from nucleus.application.remember_use_case import RememberUseCase
from nucleus.domain.constants import MutationOperation, PreviewOperation
from nucleus.domain.models import UpdateConfirmResult
from nucleus.domain.preview_token import PreviewTokenClaims, parse_preview_token
from nucleus.domain.scoping import ScopeDecision, resolve_scope_mode


@dataclass(slots=True)
class UpdateConfirmRequest:
    profile_id: str
    workspace_id: str
    preview_token: str
    selected_episode_ids: list[str]
    replacement_content: str
    source_type: str = MutationOperation.UPDATE_CONFIRM.value
    source_ref: str | None = None
    session_id: str | None = None
    turn_index: int | None = None
    speaker: str | None = None
    role: str | None = None
    observed_at: str | None = None


class UpdateConfirmUseCase:
    """Applies update confirmations after preview-token safety checks."""

    def __init__(
        self,
        *,
        episode_store: EpisodeRepository,
        remember_use_case: RememberUseCase,
    ) -> None:
        self._episode_store = episode_store
        self._remember_use_case = remember_use_case

    def execute(self, *, request: UpdateConfirmRequest) -> UpdateConfirmResult:
        """Commits an update for selected preview candidates."""
        claims, selected = self._validated_request(
            preview_token=request.preview_token,
            profile_id=request.profile_id,
            workspace_id=request.workspace_id,
            selected_episode_ids=request.selected_episode_ids,
        )
        replacement_fields = self._replacement_fields_from_request(request)
        replacement_episode_id, audit = self._apply_confirmation(
            profile_id=request.profile_id,
            workspace_id=request.workspace_id,
            claims=claims,
            selected_episode_ids=selected,
            replacement_content=request.replacement_content,
            replacement_fields=replacement_fields,
        )
        return self._confirmation_result(claims=claims, selected_episode_ids=selected, replacement_episode_id=replacement_episode_id, audit=audit)

    def _validated_request(
        self,
        *,
        preview_token: str,
        profile_id: str,
        workspace_id: str,
        selected_episode_ids: list[str],
    ) -> tuple[PreviewTokenClaims, list[str]]:
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
        return claims, selected

    def _confirmation_result(
        self,
        *,
        claims: PreviewTokenClaims,
        selected_episode_ids: list[str],
        replacement_episode_id: str,
        audit: dict[str, object],
    ) -> UpdateConfirmResult:
        scope = resolve_scope_mode(scope_mode=claims.scope_mode)
        return self._result(
            scope=scope,
            selected_episode_ids=selected_episode_ids,
            replacement_episode_id=replacement_episode_id,
            audit=audit,
        )

    @staticmethod
    def _replacement_fields(
        *,
        source_type: str,
        source_ref: str | None,
        session_id: str | None,
        turn_index: int | None,
        speaker: str | None,
        role: str | None,
        observed_at: str | None,
        ) -> dict[str, object]:
        return {
            "source_type": source_type,
            "source_ref": source_ref,
            "session_id": session_id,
            "turn_index": turn_index,
            "speaker": speaker,
            "role": role,
            "observed_at": observed_at,
        }

    @classmethod
    def _replacement_fields_from_request(cls, request: UpdateConfirmRequest) -> dict[str, object]:
        return cls._replacement_fields(source_type=request.source_type, source_ref=request.source_ref, session_id=request.session_id, turn_index=request.turn_index, speaker=request.speaker, role=request.role, observed_at=request.observed_at)

    @staticmethod
    def _validated_claims(
        *,
        preview_token: str,
        profile_id: str,
        workspace_id: str,
    ) -> PreviewTokenClaims:
        claims = parse_preview_token(preview_token)
        if claims.operation != PreviewOperation.UPDATE.value:
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
            operation=PreviewOperation.UPDATE.value,
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

    def _apply_confirmation(self, *, profile_id: str, workspace_id: str, claims: PreviewTokenClaims, selected_episode_ids: list[str], replacement_content: str, replacement_fields: dict[str, object]) -> tuple[str, dict[str, object]]:
        replacement_episode_id = self._replacement_episode_id(
            profile_id=profile_id,
            workspace_id=workspace_id,
            replacement_content=replacement_content,
            replacement_fields=replacement_fields,
        )
        audit = self._episode_store.mark_superseded(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=selected_episode_ids,
            replacement_episode_id=replacement_episode_id,
            token_id=claims.token_id,
            scope_mode=claims.scope_mode,
        )
        self._episode_store.invalidate_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation=PreviewOperation.UPDATE.value,
            scope_mode=claims.scope_mode,
            token_id=claims.token_id,
        )
        return replacement_episode_id, audit

    def _replacement_episode_id(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        replacement_content: str,
        replacement_fields: dict[str, object],
    ) -> str:
        remember_result = self._remember_use_case.execute_from_fields(
            profile_id=profile_id,
            workspace_id=workspace_id,
            content=replacement_content,
            source_type=str(replacement_fields["source_type"]),
            source_ref=self._string_field(replacement_fields, "source_ref"),
            session_id=self._string_field(replacement_fields, "session_id"),
            turn_index=self._int_field(replacement_fields, "turn_index"),
            speaker=self._string_field(replacement_fields, "speaker"),
            role=self._string_field(replacement_fields, "role"),
            observed_at=self._string_field(replacement_fields, "observed_at"),
        )
        return remember_result.episode_ids[0]

    @staticmethod
    def _string_field(values: dict[str, object], key: str) -> str | None:
        value = values.get(key)
        return value if isinstance(value, str) else None

    @staticmethod
    def _int_field(values: dict[str, object], key: str) -> int | None:
        value = values.get(key)
        return value if isinstance(value, int) else None

    @staticmethod
    def _result(
        *,
        scope: ScopeDecision,
        selected_episode_ids: list[str],
        replacement_episode_id: str,
        audit: dict[str, object],
    ) -> UpdateConfirmResult:
        return UpdateConfirmResult(
            operation=MutationOperation.UPDATE_CONFIRM.value,
            effective_scope=scope.effective_scope,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            applied_count=len(selected_episode_ids),
            superseded_episode_ids=selected_episode_ids,
            replacement_episode_id=replacement_episode_id,
            audit=audit,
        )
