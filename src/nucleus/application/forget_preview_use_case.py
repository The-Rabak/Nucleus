from __future__ import annotations

from typing import cast

from nucleus.application.ports import EpisodeRepository
from nucleus.domain.constants import (
    MutationOperation,
    PreviewOperation,
    ScopeMode,
)
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.domain.models import MutationPreviewResult, RetrieveResult
from nucleus.domain.preview_token import PreviewTokenClaims, issue_preview_token
from nucleus.domain.scoping import ScopeDecision, resolve_scope_mode

_DEFAULT_TTL_SECONDS = 300


class ForgetPreviewUseCase:
    """Builds safe forget preview candidates and short-lived selection token."""

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
        """Builds a forget preview payload for explicit user confirmation."""
        scope = self._workspace_scope(scope_mode=scope_mode)
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

    @staticmethod
    def _workspace_scope(*, scope_mode: str | None) -> ScopeDecision:
        scope = resolve_scope_mode(scope_mode=scope_mode)
        if scope.scope_widened:
            raise ValueError(
                f"{ScopeMode.PROFILE_GLOBAL.value} scope_mode is not allowed for "
                f"{MutationOperation.FORGET_PREVIEW.value}."
            )
        return scope

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
        return self._candidate_payload(results=results, integrity=integrity)

    @staticmethod
    def _candidate_payload(
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

    def _issue_preview_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        scope_mode: str,
        token_integrity: dict[str, str],
    ) -> tuple[str, PreviewTokenClaims]:
        preview_token, claims = issue_preview_token(
            operation=PreviewOperation.FORGET.value,
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope_mode,
            candidate_integrity=token_integrity,
            ttl_seconds=_DEFAULT_TTL_SECONDS,
        )
        self._register_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope_mode,
            token_id=claims.token_id,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
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
    ) -> None:
        self._episode_store.register_preview_token(
            profile_id=profile_id,
            workspace_id=workspace_id,
            operation=PreviewOperation.FORGET.value,
            scope_mode=scope_mode,
            token_id=token_id,
            issued_at=issued_at,
            expires_at=expires_at,
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
            "operation": MutationOperation.FORGET_PREVIEW.value,
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
            "operation": MutationOperation.FORGET_PREVIEW.value,
            "retrieval": retrieval_observability,
        }
