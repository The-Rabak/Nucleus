from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import uuid

from nucleus.application.checkpoint_idempotency import CheckpointIdempotency
from nucleus.application.context_packet import first_statement, redact_raw_file_path
from nucleus.application.ports import EpisodeRepository
from nucleus.application.readiness_store import ReadinessStore
from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.domain.constants import (
    ScopeMode,
    VALID_CHECKPOINT_TRIGGERS,
)
from nucleus.domain.envelopes import JsonObject
from nucleus.domain.models import EpisodeRecord, SessionCheckpointResult


class SessionCheckpointService:
    """Persists and reads durable session checkpoint snapshots."""

    def __init__(
        self,
        *,
        episode_store: EpisodeRepository,
        readiness_store: ReadinessStore,
        data_root: Path,
    ) -> None:
        self._episode_store = episode_store
        self._readiness_store = readiness_store
        self._profiles_root = (data_root / "profiles").resolve()

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
        trigger: str,
        idempotency_key: str,
        include_preview_tokens: bool = True,
    ) -> SessionCheckpointResult:
        """Creates or reuses a deterministic checkpoint for the given session."""
        request_args = self._checkpoint_request_args(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            trigger=trigger,
            idempotency_key=idempotency_key,
        )
        payload, idempotent = self._resolve_checkpoint_payload(
            include_preview_tokens=include_preview_tokens,
            **request_args,
        )
        return self._result_from_payload(payload, idempotent=idempotent)

    def _checkpoint_request_args(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
        trigger: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        safe_profile_id, safe_workspace_id, safe_session_id = self._validated_scope(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        normalized_key = self._normalized_idempotency_key(idempotency_key=idempotency_key)
        checkpoint_id, checkpoint_dir = self._checkpoint_identity(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
            session_id=safe_session_id,
            trigger=trigger,
            idempotency_key=normalized_key,
        )
        return {
            "checkpoint_dir": checkpoint_dir,
            "checkpoint_id": checkpoint_id,
            "profile_id": safe_profile_id,
            "workspace_id": safe_workspace_id,
            "trigger": trigger,
            "idempotency_key": normalized_key,
        }

    def _checkpoint_identity(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
        trigger: str,
        idempotency_key: str,
    ) -> tuple[str, Path]:
        checkpoint_id = self._checkpoint_id(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            trigger=trigger,
            idempotency_key=idempotency_key,
        )
        checkpoint_dir = self._checkpoint_dir(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        return checkpoint_id, checkpoint_dir

    def _resolve_checkpoint_payload(self, *, checkpoint_dir: Path, checkpoint_id: str, profile_id: str, workspace_id: str, trigger: str, idempotency_key: str, include_preview_tokens: bool) -> tuple[JsonObject, bool]:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_temp_files(checkpoint_dir)
        existing_payload = self._existing_checkpoint(
            checkpoint_dir=checkpoint_dir,
            checkpoint_id=checkpoint_id,
        )
        if existing_payload is not None:
            return existing_payload, True
        payload = self._new_checkpoint_payload(
            profile_id=profile_id,
            workspace_id=workspace_id,
            trigger=trigger,
            checkpoint_id=checkpoint_id,
            idempotency_key=idempotency_key,
            include_preview_tokens=include_preview_tokens,
        )
        self._persist_checkpoint_payload(
            checkpoint_dir=checkpoint_dir,
            checkpoint_id=checkpoint_id,
            payload=payload,
        )
        return payload, False

    def _persist_checkpoint_payload(
        self,
        *,
        checkpoint_dir: Path,
        checkpoint_id: str,
        payload: JsonObject,
    ) -> None:
        checkpoint_path = checkpoint_dir / f"{checkpoint_id}.json"
        self._atomic_write_json(checkpoint_path, payload)
        self._atomic_write_json(checkpoint_dir / "latest.json", payload)

    def latest_checkpoint(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
    ) -> JsonObject | None:
        """Returns the latest checkpoint payload for a session, if present."""
        safe_profile_id, safe_workspace_id, safe_session_id = self._validated_scope(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        checkpoint_dir = self._checkpoint_dir(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
            session_id=safe_session_id,
        )
        if not checkpoint_dir.exists():
            return None
        self._cleanup_temp_files(checkpoint_dir)
        latest_payload = self._safe_read_json(checkpoint_dir / "latest.json")
        if latest_payload is not None:
            return latest_payload
        return self._latest_checkpoint_from_candidates(checkpoint_dir=checkpoint_dir)

    @staticmethod
    def _validated_scope(
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
    ) -> tuple[str, str, str]:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        safe_session_id = validate_scope_identifier(name="session_id", value=session_id)
        return safe_profile_id, safe_workspace_id, safe_session_id

    @staticmethod
    def _normalized_idempotency_key(*, idempotency_key: str) -> str:
        return CheckpointIdempotency.normalize(idempotency_key)

    @staticmethod
    def _checkpoint_id(
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
        trigger: str,
        idempotency_key: str,
    ) -> str:
        if trigger not in VALID_CHECKPOINT_TRIGGERS:
            raise ValueError(
                "trigger must be one of: "
                f"{', '.join(sorted(VALID_CHECKPOINT_TRIGGERS))}."
            )
        return CheckpointIdempotency.checkpoint_id(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
            trigger=trigger,
            idempotency_key=idempotency_key,
        )

    def _existing_checkpoint(
        self,
        *,
        checkpoint_dir: Path,
        checkpoint_id: str,
    ) -> JsonObject | None:
        checkpoint_path = checkpoint_dir / f"{checkpoint_id}.json"
        existing_payload = self._safe_read_json(checkpoint_path)
        if existing_payload is None:
            return None
        latest_path = checkpoint_dir / "latest.json"
        if self._safe_read_json(latest_path) is None:
            self._atomic_write_json(latest_path, existing_payload)
        return existing_payload

    def _new_checkpoint_payload(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        trigger: str,
        checkpoint_id: str,
        idempotency_key: str,
        include_preview_tokens: bool,
    ) -> JsonObject:
        readiness = self._readiness_store.snapshot(
            profile_id=profile_id,
            workspace_id=workspace_id,
        ).to_dict()
        recent_episodes, _ = self._episode_store.list_recent(
            profile_id=profile_id,
            workspace_id=workspace_id,
            limit=3,
        )
        return {
            "checkpoint_id": checkpoint_id,
            "recorded_at": datetime.now(UTC).isoformat(),
            "effective_scope": ScopeMode.WORKSPACE_LOCAL.value,
            "readiness": readiness,
            "trigger": trigger,
            "idempotency_key": idempotency_key,
            "summary": self._build_summary(trigger=trigger, episodes=recent_episodes),
            "citations": self._build_citations(recent_episodes),
            "warnings": [] if include_preview_tokens else [self._preview_token_warning()],
        }

    @staticmethod
    def _preview_token_warning() -> str:
        return "preview tokens were excluded"

    def _latest_checkpoint_from_candidates(self, *, checkpoint_dir: Path) -> JsonObject | None:
        checkpoint_candidates = sorted(
            checkpoint_dir.glob("cp_*.json"),
            key=self._checkpoint_sort_key,
            reverse=True,
        )
        for checkpoint_path in checkpoint_candidates:
            payload = self._safe_read_json(checkpoint_path)
            if payload is None:
                continue
            self._atomic_write_json(checkpoint_dir / "latest.json", payload)
            return payload
        return None

    @staticmethod
    def _checkpoint_sort_key(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return -1.0

    def _checkpoint_dir(self, *, profile_id: str, workspace_id: str, session_id: str) -> Path:
        checkpoint_dir = (
            self._profiles_root
            / profile_id
            / "workspaces"
            / workspace_id
            / "checkpoints"
            / "sessions"
            / session_id
        )
        self._ensure_within_profiles_root(checkpoint_dir)
        return checkpoint_dir

    def _ensure_within_profiles_root(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self._profiles_root)
        except ValueError as exc:
            raise ValueError("Resolved checkpoint path escapes configured profiles root.") from exc

    def _cleanup_temp_files(self, checkpoint_dir: Path) -> None:
        for pattern in ("*.tmp", ".*.tmp"):
            for stale_file in checkpoint_dir.glob(pattern):
                stale_file.unlink(missing_ok=True)

    def _atomic_write_json(self, path: Path, payload: JsonObject) -> None:
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(payload), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _safe_read_json(path: Path) -> JsonObject | None:
        if not path.exists():
            return None
        try:
            raw_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw_payload, dict):
            return None
        return raw_payload

    @staticmethod
    def _build_summary(*, trigger: str, episodes: list[EpisodeRecord]) -> str:
        if not episodes:
            return f"Checkpoint captured via {trigger}; no recent cited memories available."
        statements = "; ".join(first_statement(episode.content, limit=120) for episode in episodes)
        return f"Checkpoint captured via {trigger}: {statements}"

    @staticmethod
    def _build_citations(episodes: list[EpisodeRecord]) -> list[JsonObject]:
        citations: list[JsonObject] = []
        for episode in episodes:
            citations.append(
                {
                    "episode_id": episode.episode_id,
                    "source_type": episode.source_type,
                    "observed_at": episode.observed_at,
                    "source_ref": episode.source_ref,
                    "session_id": episode.session_id,
                    "turn_index": episode.turn_index,
                    "raw_file_path": redact_raw_file_path(episode.raw_file_path),
                    "evidence_span": episode.content[:220],
                    "source_hash": episode.content_hash,
                }
            )
        return citations

    @staticmethod
    def _result_from_payload(payload: JsonObject, *, idempotent: bool) -> SessionCheckpointResult:
        return SessionCheckpointResult(
            checkpoint_id=str(payload["checkpoint_id"]),
            recorded_at=str(payload["recorded_at"]),
            effective_scope=str(payload["effective_scope"]),
            readiness=dict(payload["readiness"]),
            trigger=str(payload["trigger"]),
            idempotency_key=str(payload["idempotency_key"]),
            summary=str(payload["summary"]),
            citations=list(payload["citations"]),
            warnings=list(payload.get("warnings", [])),
            idempotent=idempotent,
        )
