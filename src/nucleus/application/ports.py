from __future__ import annotations

from typing import Protocol

from nucleus.domain.models import EpisodeRecord


class EpisodeRepository(Protocol):
    def persist_episode(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        source_type: str,
        content: str,
        source_ref: str | None,
        session_id: str | None,
        turn_index: int | None,
        speaker: str | None,
        role: str | None,
        observed_at: str | None,
    ) -> EpisodeRecord: ...

    def list_recent(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        limit: int = 3,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]: ...

    def search(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int = 5,
        scope_mode: str = "workspace_local",
    ) -> tuple[list[EpisodeRecord], dict[str, int]]: ...
