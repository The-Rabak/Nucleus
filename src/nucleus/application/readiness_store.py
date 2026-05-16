from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import uuid

from nucleus.application.scope_validation import validate_scope_identifier

@dataclass(slots=True)
class ReadinessSnapshot:
    ready: bool
    index_status: str
    readiness_hint: str
    truthful: bool = True

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "ready": self.ready,
            "index_status": self.index_status,
            "readiness_hint": self.readiness_hint,
            "truthful": self.truthful,
        }


class ReadinessStore:
    def __init__(self, *, data_root: Path) -> None:
        self._data_root = data_root
        self._profiles_root = (self._data_root / "profiles").resolve()

    def mark_index_pending(self, *, profile_id: str, workspace_id: str) -> None:
        snapshot = ReadinessSnapshot(
            ready=False,
            index_status="pending",
            readiness_hint="Indexing pending; retrieval may rely on raw cited fallback.",
        )
        self._write_snapshot(
            profile_id=profile_id,
            workspace_id=workspace_id,
            snapshot=snapshot,
        )

    def snapshot(self, *, profile_id: str, workspace_id: str) -> ReadinessSnapshot:
        state_path = self._state_file_path(profile_id=profile_id, workspace_id=workspace_id)
        if not state_path.exists():
            return self._default_ready_snapshot()

        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ReadinessSnapshot(
                ready=False,
                index_status="partial",
                readiness_hint="Readiness state is degraded because persisted snapshot is unreadable.",
            )

        return ReadinessSnapshot(
            ready=bool(payload.get("ready", True)),
            index_status=str(payload.get("index_status", "ready")),
            readiness_hint=str(payload.get("readiness_hint", self._default_ready_snapshot().readiness_hint)),
            truthful=bool(payload.get("truthful", True)),
        )

    def _state_file_path(self, *, profile_id: str, workspace_id: str) -> Path:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        state_path = (
            self._profiles_root
            / safe_profile_id
            / "workspaces"
            / safe_workspace_id
            / "readiness.json"
        )
        state_path.parent.mkdir(parents=True, exist_ok=True)
        resolved = state_path.resolve()
        try:
            resolved.relative_to(self._profiles_root)
        except ValueError as exc:
            raise ValueError("Resolved readiness path escapes configured profiles root.") from exc
        return resolved

    def _write_snapshot(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        snapshot: ReadinessSnapshot,
    ) -> None:
        state_path = self._state_file_path(profile_id=profile_id, workspace_id=workspace_id)
        temp_path = state_path.with_name(f".{state_path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")
        temp_path.replace(state_path)

    @staticmethod
    def _default_ready_snapshot() -> ReadinessSnapshot:
        return ReadinessSnapshot(
            ready=True,
            index_status="ready",
            readiness_hint=f"Ready as of {datetime.now(UTC).isoformat()} (no pending indexing backlog).",
        )
