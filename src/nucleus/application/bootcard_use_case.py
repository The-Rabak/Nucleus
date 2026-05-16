from __future__ import annotations

import time
from typing import TYPE_CHECKING

from nucleus.application.context_packet import build_bootcard_context_packet, first_statement
from nucleus.application.ports import EpisodeRepository
from nucleus.application.readiness_store import ReadinessStore
from nucleus.domain.constants import ScopeMode, Stage1Operation
from nucleus.domain.models import Bootcard, EpisodeRecord
from nucleus.domain.scoping import ScopeDecision, workspace_local_scope

if TYPE_CHECKING:
    from nucleus.application.inspect_status_use_case import InspectStatusUseCase


class BootcardUseCase:
    """Builds Stage 1 bootstrap context and summarized memory map."""

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
        """Returns startup markdown, context packet, readiness, and observability."""
        scope = workspace_local_scope()
        readiness = self._readiness(profile_id=profile_id, workspace_id=workspace_id)
        recent_episodes, scan_counters, duration_ms = self._recent_episodes(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        latest_checkpoint = self._latest_checkpoint(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        return self._bootcard_with_markdown(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            readiness=readiness,
            recent_episodes=recent_episodes,
            latest_checkpoint=latest_checkpoint,
            duration_ms=duration_ms,
            scan_counters=scan_counters,
            scope=scope,
        )

    def _bootcard_with_markdown(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
        readiness: dict[str, object],
        recent_episodes: list[EpisodeRecord],
        latest_checkpoint: dict[str, object] | None,
        duration_ms: float,
        scan_counters: dict[str, int],
        scope: ScopeDecision,
    ) -> Bootcard:
        markdown = self._build_markdown(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            readiness=readiness,
            recent_episodes=recent_episodes,
            latest_checkpoint=latest_checkpoint,
            scope_policy=scope.scope_policy,
        )
        return self._bootcard_response(
            markdown=markdown,
            recent_episodes=recent_episodes,
            readiness=readiness,
            duration_ms=duration_ms,
            scan_counters=scan_counters,
            scope=scope,
        )

    def _readiness(self, *, profile_id: str, workspace_id: str) -> dict[str, object]:
        return self._readiness_store.snapshot(
            profile_id=profile_id,
            workspace_id=workspace_id,
        ).to_dict()

    def _recent_episodes(
        self,
        *,
        profile_id: str,
        workspace_id: str,
    ) -> tuple[list[EpisodeRecord], dict[str, int], float]:
        started_at = time.perf_counter()
        episodes, scan_counters = self._episode_store.list_recent(
            profile_id=profile_id,
            workspace_id=workspace_id,
            limit=3,
        )
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        return episodes, scan_counters, duration_ms

    def _latest_checkpoint(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
    ) -> dict[str, object] | None:
        if session_id is None or self._inspect_status_use_case is None:
            return None
        return self._inspect_status_use_case.execute(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        ).latest_checkpoint

    @staticmethod
    def _bootcard_response(
        *,
        markdown: str,
        recent_episodes: list[EpisodeRecord],
        readiness: dict[str, object],
        duration_ms: float,
        scan_counters: dict[str, int],
        scope: ScopeDecision,
    ) -> Bootcard:
        return Bootcard(
            markdown=markdown,
            context_packet=build_bootcard_context_packet(episodes=recent_episodes),
            readiness=readiness,
            effective_scope=scope.effective_scope,
            scope_widened=scope.scope_widened,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            observability={
                "operation": Stage1Operation.BOOTCARD.value,
                "duration_ms": duration_ms,
                "scan_counters": scan_counters,
                "scope": scope.to_dict(),
            },
        )

    @classmethod
    def _build_markdown(
        cls,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
        readiness: dict[str, object],
        recent_episodes: list[EpisodeRecord],
        latest_checkpoint: dict[str, object] | None,
        scope_policy: str,
    ) -> str:
        lines = cls._header_lines(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            readiness=readiness,
            scope_policy=scope_policy,
        )
        lines.extend(["", "### Retrieval protocol", *cls._retrieval_protocol_lines()])
        lines.extend(["", "### Session summary", *cls._session_summary_lines(latest_checkpoint)])
        lines.extend(["", "### Memory map", *cls._memory_lines(recent_episodes), ""])
        return "\n".join(lines)

    @staticmethod
    def _header_lines(
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str | None,
        readiness: dict[str, object],
        scope_policy: str,
    ) -> list[str]:
        return [
            "## Nucleus Bootstrap",
            "",
            f"- profile_id: {profile_id}",
            f"- workspace_id: {workspace_id}",
            f"- session_id: {session_id or 'unknown'}",
            f"- effective_scope: {ScopeMode.WORKSPACE_LOCAL.value}",
            f"- widening_policy: {scope_policy}",
            f"- profile_global_widening: explicit via scope_mode={ScopeMode.PROFILE_GLOBAL.value}",
            f"- readiness: {readiness['index_status']} ({readiness['readiness_hint']})",
        ]

    @staticmethod
    def _retrieval_protocol_lines() -> list[str]:
        return [
            "- Use remember() to persist a source episode.",
            "- Use retrieve() to fetch cited evidence and a fenced context packet.",
        ]

    @staticmethod
    def _session_summary_lines(latest_checkpoint: dict[str, object] | None) -> list[str]:
        if latest_checkpoint is None:
            return ["- Stage 1 tracer bullet startup context initialized."]
        trigger = latest_checkpoint.get("trigger", "unknown")
        checkpoint_id = latest_checkpoint.get("checkpoint_id", "unknown")
        summary = latest_checkpoint.get("summary", "No checkpoint summary recorded.")
        return [f"- Latest checkpoint ({trigger}): {summary} (checkpoint: {checkpoint_id})"]

    @staticmethod
    def _memory_lines(recent_episodes: list[EpisodeRecord]) -> list[str]:
        if not recent_episodes:
            return ["- No recent memories yet."]
        return [
            f"- {first_statement(episode.content, limit=120)} (episode: {episode.episode_id})"
            for episode in recent_episodes
        ]
