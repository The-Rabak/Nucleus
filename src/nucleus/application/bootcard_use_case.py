from __future__ import annotations

import time
from typing import TYPE_CHECKING

from nucleus.application.context_packet import build_bootcard_context_packet, first_statement
from nucleus.application.ports import EpisodeRepository
from nucleus.application.readiness_store import ReadinessStore
from nucleus.domain.models import Bootcard, EpisodeRecord
from nucleus.domain.scoping import workspace_local_scope

if TYPE_CHECKING:
    from nucleus.application.inspect_status_use_case import InspectStatusUseCase


class BootcardUseCase:
    def __init__(
        self,
        *,
        episode_store: EpisodeRepository,
        readiness_store: ReadinessStore,
        inspect_status_use_case: InspectStatusUseCase | None = None,
    ) -> None:
        self._episode_store = episode_store
        self._readiness_store = readiness_store
        self._inspect_status_use_case = inspect_status_use_case

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
    ) -> Bootcard:
        scope = workspace_local_scope()
        readiness = self._readiness_store.snapshot(
            profile_id=profile_id,
            workspace_id=workspace_id,
        ).to_dict()
        operation_started_at = time.perf_counter()
        recent_episodes, scan_counters = self._episode_store.list_recent(
            profile_id=profile_id,
            workspace_id=workspace_id,
            limit=3,
        )
        operation_duration_ms = round((time.perf_counter() - operation_started_at) * 1000, 3)
        latest_checkpoint: dict[str, object] | None = None
        if session_id is not None and self._inspect_status_use_case is not None:
            latest_checkpoint = self._inspect_status_use_case.execute(
                profile_id=profile_id,
                workspace_id=workspace_id,
                session_id=session_id,
            ).latest_checkpoint

        context_packet = build_bootcard_context_packet(episodes=recent_episodes)
        markdown = self._build_markdown(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            readiness=readiness,
            recent_episodes=recent_episodes,
            latest_checkpoint=latest_checkpoint,
            scope_policy=scope.scope_policy,
        )

        return Bootcard(
            markdown=markdown,
            context_packet=context_packet,
            readiness=readiness,
            effective_scope=scope.effective_scope,
            scope_widened=scope.scope_widened,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            observability={
                "operation": "bootcard",
                "duration_ms": operation_duration_ms,
                "scan_counters": scan_counters,
                "scope": scope.to_dict(),
            },
        )

    @staticmethod
    def _build_markdown(
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
        readiness: dict[str, object],
        recent_episodes: list[EpisodeRecord],
        latest_checkpoint: dict[str, object] | None,
        scope_policy: str,
    ) -> str:
        memory_lines = ["- No recent memories yet."]
        if recent_episodes:
            memory_lines = [
                f"- {first_statement(episode.content, limit=120)} (episode: {episode.episode_id})"
                for episode in recent_episodes
            ]
        session_summary_lines = ["- Stage 1 tracer bullet startup context initialized."]
        if latest_checkpoint is not None:
            trigger = latest_checkpoint.get("trigger", "unknown")
            checkpoint_id = latest_checkpoint.get("checkpoint_id", "unknown")
            summary = latest_checkpoint.get("summary", "No checkpoint summary recorded.")
            session_summary_lines = [
                f"- Latest checkpoint ({trigger}): {summary} (checkpoint: {checkpoint_id})"
            ]

        lines = [
            "## Nucleus Bootstrap",
            "",
            f"- profile_id: {profile_id}",
            f"- workspace_id: {workspace_id}",
            f"- session_id: {session_id or 'unknown'}",
            "- effective_scope: workspace_local",
            f"- widening_policy: {scope_policy}",
            "- profile_global_widening: explicit via scope_mode=profile_global",
            f"- readiness: {readiness['index_status']} ({readiness['readiness_hint']})",
            "",
            "### Retrieval protocol",
            "- Use remember() to persist a source episode.",
            "- Use retrieve() to fetch cited evidence and a fenced context packet.",
            "",
            "### Session summary",
            *session_summary_lines,
            "",
            "### Memory map",
            *memory_lines,
            "",
        ]
        return "\n".join(lines)
