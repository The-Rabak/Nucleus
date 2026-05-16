from __future__ import annotations

import uuid
from dataclasses import dataclass

from nucleus.application.ports import EpisodeRepository
from nucleus.application.readiness_store import ReadinessStore
from nucleus.domain.models import RememberResult


@dataclass(slots=True)
class RememberRequest:
    profile_id: str
    workspace_id: str
    source_type: str
    content: str
    source_ref: str | None = None
    session_id: str | None = None
    turn_index: int | None = None
    speaker: str | None = None
    role: str | None = None
    observed_at: str | None = None


class RememberUseCase:
    def __init__(self, *, episode_store: EpisodeRepository, readiness_store: ReadinessStore) -> None:
        self._episode_store = episode_store
        self._readiness_store = readiness_store

    def execute(
        self,
        *,
        request: RememberRequest,
    ) -> RememberResult:
        episode = self._episode_store.persist_episode(
            profile_id=request.profile_id,
            workspace_id=request.workspace_id,
            source_type=request.source_type,
            content=request.content,
            source_ref=request.source_ref,
            session_id=request.session_id,
            turn_index=request.turn_index,
            speaker=request.speaker,
            role=request.role,
            observed_at=request.observed_at,
        )

        self._readiness_store.mark_index_pending(
            profile_id=request.profile_id,
            workspace_id=request.workspace_id,
        )

        return RememberResult(
            ingest_id=f"ing_{uuid.uuid4().hex[:12]}",
            episode_ids=[episode.episode_id],
            index_status="pending",
            readiness_hint="Indexing pending; retrieval may rely on raw cited fallback.",
        )

    def execute_from_fields(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        source_type: str,
        content: str,
        source_ref: str | None = None,
        session_id: str | None = None,
        turn_index: int | None = None,
        speaker: str | None = None,
        role: str | None = None,
        observed_at: str | None = None,
    ) -> RememberResult:
        return self.execute(
            request=RememberRequest(
                profile_id=profile_id,
                workspace_id=workspace_id,
                source_type=source_type,
                content=content,
                source_ref=source_ref,
                session_id=session_id,
                turn_index=turn_index,
                speaker=speaker,
                role=role,
                observed_at=observed_at,
            )
        )
