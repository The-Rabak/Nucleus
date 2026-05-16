from __future__ import annotations

from nucleus.application.readiness_store import ReadinessStore
from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.application.session_checkpoint_service import SessionCheckpointService
from nucleus.domain.models import InspectStatusResult
from nucleus.domain.scoping import workspace_local_scope


class InspectStatusUseCase:
    """Provides scoped readiness and checkpoint diagnostics."""

    def __init__(
        self,
        *,
        readiness_store: ReadinessStore,
        checkpoint_service: SessionCheckpointService,
    ) -> None:
        self._readiness_store = readiness_store
        self._checkpoint_service = checkpoint_service

    def execute(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
    ) -> InspectStatusResult:
        scope = workspace_local_scope()
        safe_profile_id, safe_workspace_id, safe_session_id = self._validated_scope(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
        readiness = self._readiness(profile_id=safe_profile_id, workspace_id=safe_workspace_id)
        latest_checkpoint = self._latest_checkpoint(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
            session_id=safe_session_id,
        )
        return InspectStatusResult(
            effective_scope=scope.effective_scope,
            scope_widened=scope.scope_widened,
            requested_scope_mode=scope.requested_scope_mode,
            scope_policy=scope.scope_policy,
            readiness=readiness,
            latest_checkpoint=latest_checkpoint,
            warnings=[],
        )

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

    def _readiness(self, *, profile_id: str, workspace_id: str) -> dict[str, object]:
        return self._readiness_store.snapshot(
            profile_id=profile_id,
            workspace_id=workspace_id,
        ).to_dict()

    def _latest_checkpoint(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        session_id: str,
    ) -> dict[str, object] | None:
        return self._checkpoint_service.latest_checkpoint(
            profile_id=profile_id,
            workspace_id=workspace_id,
            session_id=session_id,
        )
