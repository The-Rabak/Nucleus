from __future__ import annotations

from typing import cast

from nucleus.application.ports import EpisodeRepository
from nucleus.application.preview_confirm_safety import (
    build_preview_candidate_payload,
    resolve_preview_workspace_scope,
)
from nucleus.domain.constants import MutationOperation, PreviewOperation
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.domain.models import MutationPreviewResult, RetrieveResult
from nucleus.domain.preview_token import (
    PreviewTokenClaims,
    issue_preview_token,
    preview_token_claims_digest,
)
_DEFAULT_TTL_SECONDS = 300


class UpdatePreviewUseCase:
    """Builds safe update preview candidates and short-lived selection token."""

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
        """Builds an update preview payload for explicit user confirmation."""
        scope = resolve_preview_workspace_scope(
            scope_mode=scope_mode,
            operation=MutationOperation.UPDATE_PREVIEW.value,
        )
        result_args = self._preview_result_args(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            scope_mode=scope.effective_scope,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
        )
        return self._result(**result_args)

    def _preview_result_args(self, *, profile_id: str, workspace_id: str, query: str, top_k: int, scope_mode: str, requested_scope_mode: str, scope_policy: str) -> dict[str, object]:
        retrieve_result, candidates, candidate_integrity, token_integrity = self._preview_candidates(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            retrieval_scope_mode=requested_scope_mode,
            integrity_scope_mode=scope_mode,
        )
        preview_token, claims = self._issue_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope_mode,
            token_integrity=token_integrity,
        )
        return self._result_args_payload(
            preview_token=preview_token,
            claims=claims,
            scope_mode=scope_mode,
            requested_scope_mode=requested_scope_mode,
            scope_policy=scope_policy,
            profile_id=profile_id,
            workspace_id=workspace_id,
            candidates=candidates,
            candidate_integrity=candidate_integrity,
            retrieval_observability=retrieve_result.observability,
        )

    def _preview_candidates(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int,
        retrieval_scope_mode: str,
        integrity_scope_mode: str,
    ) -> tuple[RetrieveResult, list[dict[str, object]], dict[str, dict[str, str]], dict[str, str]]:
        retrieve_result = self._retrieve(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            scope_mode=retrieval_scope_mode,
        )
        candidates, candidate_integrity, token_integrity = self._candidates(
            retrieve_result=retrieve_result,
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=integrity_scope_mode,
        )
        return retrieve_result, candidates, candidate_integrity, token_integrity

    @staticmethod
    def _result_args_payload(
        *,
        preview_token: str,
        claims: PreviewTokenClaims,
        scope_mode: str,
        requested_scope_mode: str,
        scope_policy: str,
        profile_id: str,
        workspace_id: str,
        candidates: list[dict[str, object]],
        candidate_integrity: dict[str, dict[str, str]],
        retrieval_observability: dict[str, object],
    ) -> dict[str, object]:
        return {
            "preview_token": preview_token,
            "claims": claims,
            "scope_mode": scope_mode,
            "requested_scope_mode": requested_scope_mode,
            "scope_policy": scope_policy,
            "profile_id": profile_id,
            "workspace_id": workspace_id,
            "candidates": candidates,
            "candidate_integrity": candidate_integrity,
            "retrieval_observability": retrieval_observability,
        }

    def _retrieve(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int,
        scope_mode: str,
    ) -> RetrieveResult:
        return self._retrieve_use_case.execute(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            scope_mode=scope_mode,
        )

    def _candidates(
        self,
        *,
        retrieve_result: RetrieveResult,
        profile_id: str,
        workspace_id: str,
        scope_mode: str,
    ) -> tuple[list[dict[str, object]], dict[str, dict[str, str]], dict[str, str]]:
        results = retrieve_result.results
        candidate_ids = [str(cast(dict[str, object], item["citation"])["episode_id"]) for item in results]
        integrity = self._episode_store.candidate_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=candidate_ids,
            scope_mode=scope_mode,
        )
        return build_preview_candidate_payload(results=results, integrity=integrity)

    def _issue_preview_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        scope_mode: str,
        token_integrity: dict[str, str],
    ) -> tuple[str, PreviewTokenClaims]:
        signing_key = self._episode_store.preview_token_signing_key(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        preview_token, claims = issue_preview_token(
            operation=PreviewOperation.UPDATE.value,
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope_mode,
            candidate_integrity=token_integrity,
            ttl_seconds=_DEFAULT_TTL_SECONDS,
            signing_key=signing_key,
        )
        self._register_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope_mode,
            token_id=claims.token_id,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
            claims_digest=preview_token_claims_digest(claims),
        )
        return preview_token, claims

    def _register_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        scope_mode: str,
        token_id: str,
        issued_at: str,
        expires_at: str,
        claims_digest: str,
    ) -> None:
        self._episode_store.register_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation=PreviewOperation.UPDATE.value,
            scope_mode=scope_mode,
            token_id=token_id,
            issued_at=issued_at,
            expires_at=expires_at,
            claims_digest=claims_digest,
        )

    @classmethod
    def _result(
        cls,
        *,
        preview_token: str,
        claims: PreviewTokenClaims,
        scope_mode: str,
        requested_scope_mode: str,
        scope_policy: str,
        profile_id: str,
        workspace_id: str,
        candidates: list[dict[str, object]],
        candidate_integrity: dict[str, dict[str, str]],
        retrieval_observability: dict[str, object],
    ) -> MutationPreviewResult:
        payload = cls._result_payload(
            preview_token=preview_token,
            claims=claims,
            scope_mode=scope_mode,
            requested_scope_mode=requested_scope_mode,
            scope_policy=scope_policy,
            profile_id=profile_id,
            workspace_id=workspace_id,
            candidates=candidates,
            candidate_integrity=candidate_integrity,
            retrieval_observability=retrieval_observability,
        )
        return MutationPreviewResult(**payload)

    @classmethod
    def _result_payload(
        cls,
        *,
        preview_token: str,
        claims: PreviewTokenClaims,
        scope_mode: str,
        requested_scope_mode: str,
        scope_policy: str,
        profile_id: str,
        workspace_id: str,
        candidates: list[dict[str, object]],
        candidate_integrity: dict[str, dict[str, str]],
        retrieval_observability: dict[str, object],
    ) -> dict[str, object]:
        return {
            "operation": MutationOperation.UPDATE_PREVIEW.value,
            "preview_token": preview_token,
            "token_id": claims.token_id,
            "issued_at": claims.issued_at,
            "expires_at": claims.expires_at,
            "ttl_seconds": _DEFAULT_TTL_SECONDS,
            "effective_scope": scope_mode,
            "requested_scope_mode": requested_scope_mode,
            "scope_policy": scope_policy,
            "scope": cls._scope_payload(profile_id=profile_id, workspace_id=workspace_id, scope_mode=scope_mode),
            "selection": cls._selection_payload(candidates=candidates),
            "candidates": candidates,
            "candidate_integrity": candidate_integrity,
            "observability": cls._observability_payload(retrieval_observability=retrieval_observability),
        }

    @staticmethod
    def _scope_payload(*, profile_id: str, workspace_id: str, scope_mode: str) -> dict[str, str]:
        return {
            "profile_id": profile_id,
            "workspace_id": workspace_id,
            "scope_mode": scope_mode,
        }

    @staticmethod
    def _selection_payload(*, candidates: list[dict[str, object]]) -> dict[str, object]:
        return {
            "requires_explicit_ids": True,
            "minimum_selected": 1,
            "allowed_candidate_ids": [candidate["episode_id"] for candidate in candidates],
        }

    @staticmethod
    def _observability_payload(*, retrieval_observability: dict[str, object]) -> dict[str, object]:
        return {
            "operation": MutationOperation.UPDATE_PREVIEW.value,
            "retrieval": retrieval_observability,
        }
