from __future__ import annotations

from datetime import datetime
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

    def candidate_integrity(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        scope_mode: str = "workspace_local",
    ) -> dict[str, dict[str, str]]: ...

    def register_preview_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        operation: str,
        scope_mode: str,
        token_id: str,
        issued_at: str,
        expires_at: str,
    ) -> None: ...

    def is_preview_token_active(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        operation: str,
        scope_mode: str,
        token_id: str,
        now: datetime,
    ) -> bool: ...

    def invalidate_preview_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        operation: str,
        scope_mode: str,
        token_id: str,
    ) -> None: ...

    def mark_superseded(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        replacement_episode_id: str,
        token_id: str,
        scope_mode: str,
    ) -> dict[str, object]: ...

    def mark_forgotten(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        token_id: str,
        scope_mode: str,
    ) -> dict[str, object]: ...
