from __future__ import annotations

from typing import cast

from nucleus.application.ports import EpisodeRepository
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.domain.models import MutationPreviewResult
from nucleus.domain.preview_token import issue_preview_token
from nucleus.domain.scoping import resolve_scope_mode

_DEFAULT_TTL_SECONDS = 300


class UpdatePreviewUseCase:
    def __init__(
        self,
        *,
        retrieve_use_case: RetrieveUseCase,
        episode_store: EpisodeRepository,
    ) -> None:
        self._retrieve_use_case = retrieve_use_case
        self._episode_store = episode_store

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int = 5,
        scope_mode: str | None = None,
    ) -> MutationPreviewResult:
        scope = resolve_scope_mode(scope_mode=scope_mode)
        if scope.scope_widened:
            raise ValueError("profile_global scope_mode is not allowed for update_preview.")

        retrieve_result = self._retrieve_use_case.execute(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            scope_mode=scope.requested_scope_mode,
        )

        candidate_ids = [
            str(cast(dict[str, object], result["citation"])["episode_id"])
            for result in retrieve_result.results
        ]
        integrity = self._episode_store.candidate_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=candidate_ids,
            scope_mode=scope.effective_scope,
        )

        candidates: list[dict[str, object]] = []
        candidate_integrity: dict[str, dict[str, str]] = {}
        token_integrity: dict[str, str] = {}
        for result in retrieve_result.results:
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

        preview_token, claims = issue_preview_token(
            operation="update",
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope.effective_scope,
            candidate_integrity=token_integrity,
            ttl_seconds=_DEFAULT_TTL_SECONDS,
        )
        self._episode_store.register_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation="update",
            scope_mode=scope.effective_scope,
            token_id=claims.token_id,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
        )

        return MutationPreviewResult(
            operation="update_preview",
            preview_token=preview_token,
            token_id=claims.token_id,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
            ttl_seconds=_DEFAULT_TTL_SECONDS,
            effective_scope=scope.effective_scope,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            scope={
                "profile_id": profile_id,
                "workspace_id": workspace_id,
                "scope_mode": scope.effective_scope,
            },
            selection={
                "requires_explicit_ids": True,
                "minimum_selected": 1,
                "allowed_candidate_ids": [candidate["episode_id"] for candidate in candidates],
            },
            candidates=candidates,
            candidate_integrity=candidate_integrity,
            observability={
                "operation": "update_preview",
                "retrieval": retrieve_result.observability,
            },
        )
