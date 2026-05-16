from __future__ import annotations

import time
import uuid

from nucleus.application.context_packet import (
    build_retrieve_context_packet,
    first_statement,
    redact_raw_file_path,
)
from nucleus.application.ports import EpisodeRepository
from nucleus.application.readiness_store import ReadinessStore
from nucleus.domain.constants import Stage1Operation
from nucleus.domain.models import EpisodeRecord, RetrieveResult
from nucleus.domain.scoping import ScopeDecision, resolve_scope_mode

_MAX_TOP_K = 10
_MAX_QUERY_LENGTH = 500


class RetrieveUseCase:
    """Retrieves cited memory results with explicit scope metadata."""

    def __init__(self, *, episode_store: EpisodeRepository, readiness_store: ReadinessStore) -> None:
        self._episode_store = episode_store
        self._readiness_store = readiness_store

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int = 5,
        scope_mode: str | None = None,
    ) -> RetrieveResult:
        self._validate_request(query=query, top_k=top_k)
        scope = resolve_scope_mode(scope_mode=scope_mode)
        episodes, scan_counters, operation_duration_ms = self._search(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            effective_scope=scope.effective_scope,
        )
        readiness = self._readiness(profile_id=profile_id, workspace_id=workspace_id)
        return self._build_result(
            episodes=episodes,
            scan_counters=scan_counters,
            operation_duration_ms=operation_duration_ms,
            scope=scope,
            readiness=readiness,
        )

    @staticmethod
    def _validate_request(*, query: str, top_k: int) -> None:
        if top_k < 1 or top_k > _MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {_MAX_TOP_K}.")
        if len(query) > _MAX_QUERY_LENGTH:
            raise ValueError(f"query must be <= {_MAX_QUERY_LENGTH} characters.")

    def _search(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int,
        effective_scope: str,
    ) -> tuple[list[EpisodeRecord], dict[str, int], float]:
        operation_started_at = time.perf_counter()
        episodes, scan_counters = self._episode_store.search(
            profile_id=profile_id,
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            scope_mode=effective_scope,
        )
        duration_ms = round((time.perf_counter() - operation_started_at) * 1000, 3)
        return episodes, scan_counters, duration_ms

    def _readiness(self, *, profile_id: str, workspace_id: str) -> dict[str, object]:
        return self._readiness_store.snapshot(
            profile_id=profile_id,
            workspace_id=workspace_id,
        ).to_dict()

    def _build_result(
        self,
        *,
        episodes: list[EpisodeRecord],
        scan_counters: dict[str, int],
        operation_duration_ms: float,
        scope: ScopeDecision,
        readiness: dict[str, object],
    ) -> RetrieveResult:
        results = [self._to_memory_result(item) for item in episodes]
        evidence_status = "found" if results else "none"
        return RetrieveResult(
            retrieval_id=f"ret_{uuid.uuid4().hex[:12]}",
            evidence_status=evidence_status,
            effective_scope=scope.effective_scope,
            scope_widened=scope.scope_widened,
            results=results,
            context_packet=build_retrieve_context_packet(episodes=episodes),
            readiness=readiness,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            observability={
                "operation": Stage1Operation.RETRIEVE.value,
                "visibility_policy": "active_only",
                "duration_ms": operation_duration_ms,
                "scan_counters": scan_counters,
                "scope": scope.to_dict(),
            },
        )

    @staticmethod
    def _to_memory_result(episode: EpisodeRecord) -> dict[str, object]:
        statement = first_statement(episode.content, limit=200)
        citation = {
            "episode_id": episode.episode_id,
            "evidence_span": episode.content[:220],
            "speaker": episode.speaker,
            "role": episode.role,
            "observed_at": episode.observed_at,
            "source_type": episode.source_type,
            "source_ref": episode.source_ref,
            "session_id": episode.session_id,
            "turn_index": episode.turn_index,
            "raw_file_path": redact_raw_file_path(episode.raw_file_path),
            "source_hash": episode.content_hash,
            "evidence_capsule_id": None,
        }
        return {
            "memory_id": f"mem_{episode.episode_id}",
            "statement": statement,
            "canonical_type": "episode_observation",
            "attributes": {},
            "score_breakdown": {
                "channel": "raw_fallback",
                "score": 1.0,
            },
            "citation": citation,
            "status": "pending_unverified",
            "channel_provenance": ["raw_fallback"],
        }
