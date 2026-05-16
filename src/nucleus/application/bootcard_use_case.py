from __future__ import annotations

import time

from nucleus.application.context_packet import build_bootcard_context_packet, first_statement
from nucleus.application.ports import EpisodeRepository
from nucleus.application.readiness_store import ReadinessStore
from nucleus.domain.models import Bootcard, EpisodeRecord


class BootcardUseCase:
    def __init__(self, *, episode_store: EpisodeRepository, readiness_store: ReadinessStore) -> None:
        self._episode_store = episode_store
        self._readiness_store = readiness_store

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
    ) -> Bootcard:
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

        context_packet = build_bootcard_context_packet(episodes=recent_episodes)
        markdown = self._build_markdown(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            readiness=readiness,
            recent_episodes=recent_episodes,
        )

        return Bootcard(
            markdown=markdown,
            context_packet=context_packet,
            readiness=readiness,
            observability={
                "operation": "bootcard",
                "duration_ms": operation_duration_ms,
                "scan_counters": scan_counters,
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
    ) -> str:
        memory_lines = ["- No recent memories yet."]
        if recent_episodes:
            memory_lines = [
                f"- {first_statement(episode.content, limit=120)} (episode: {episode.episode_id})"
                for episode in recent_episodes
            ]

        lines = [
            "## Nucleus Bootstrap",
            "",
            f"- profile_id: {profile_id}",
            f"- workspace_id: {workspace_id}",
            f"- session_id: {session_id or 'unknown'}",
            "- effective_scope: workspace_local",
            f"- readiness: {readiness['index_status']} ({readiness['readiness_hint']})",
            "",
            "### Retrieval protocol",
            "- Use remember() to persist a source episode.",
            "- Use retrieve() to fetch cited evidence and a fenced context packet.",
            "",
            "### Session summary",
            "- Stage 1 tracer bullet startup context initialized.",
            "",
            "### Memory map",
            *memory_lines,
            "",
        ]
        return "\n".join(lines)
