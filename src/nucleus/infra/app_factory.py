from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nucleus.adapters.filesystem.episode_store import EpisodeStore
from nucleus.adapters.http.api import NucleusHTTPAPI
from nucleus.adapters.mcp.server import NucleusMCPServer, NucleusOperationAdapter
from nucleus.application.bootcard_use_case import BootcardUseCase
from nucleus.application.forget_confirm_use_case import ForgetConfirmUseCase
from nucleus.application.forget_preview_use_case import ForgetPreviewUseCase
from nucleus.application.inspect_status_use_case import InspectStatusUseCase
from nucleus.application.readiness_store import ReadinessStore
from nucleus.application.remember_use_case import RememberUseCase
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.application.session_checkpoint_service import SessionCheckpointService
from nucleus.application.update_confirm_use_case import UpdateConfirmUseCase
from nucleus.application.update_preview_use_case import UpdatePreviewUseCase
from nucleus.infra.runtime_config import RuntimeConfig, load_runtime_config


@dataclass(slots=True)
class NucleusApp:
    remember: RememberUseCase
    retrieve: RetrieveUseCase
    update_preview: UpdatePreviewUseCase
    update_confirm: UpdateConfirmUseCase
    forget_preview: ForgetPreviewUseCase
    forget_confirm: ForgetConfirmUseCase
    checkpoint_session: SessionCheckpointService
    inspect_status: InspectStatusUseCase
    bootcard: BootcardUseCase
    mcp_server: NucleusMCPServer
    http_api: NucleusHTTPAPI


def create_app(
    *,
    data_root: Path | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> NucleusApp:
    resolved_runtime_config = runtime_config or load_runtime_config(data_root=data_root)
    episode_store = EpisodeStore(data_root=resolved_runtime_config.data_dir)
    readiness_store = ReadinessStore(data_root=resolved_runtime_config.data_dir)

    remember_use_case = RememberUseCase(
        episode_store=episode_store,
        readiness_store=readiness_store,
    )
    retrieve_use_case = RetrieveUseCase(
        episode_store=episode_store,
        readiness_store=readiness_store,
    )
    update_preview_use_case = UpdatePreviewUseCase(
        retrieve_use_case=retrieve_use_case,
        episode_store=episode_store,
    )
    update_confirm_use_case = UpdateConfirmUseCase(
        episode_store=episode_store,
        remember_use_case=remember_use_case,
    )
    forget_preview_use_case = ForgetPreviewUseCase(
        retrieve_use_case=retrieve_use_case,
        episode_store=episode_store,
    )
    forget_confirm_use_case = ForgetConfirmUseCase(
        episode_store=episode_store,
    )
    checkpoint_service = SessionCheckpointService(
        episode_store=episode_store,
        readiness_store=readiness_store,
        data_root=resolved_runtime_config.data_dir,
    )
    inspect_status_use_case = InspectStatusUseCase(
        readiness_store=readiness_store,
        checkpoint_service=checkpoint_service,
    )
    bootcard_use_case = BootcardUseCase(
        episode_store=episode_store,
        readiness_store=readiness_store,
        inspect_status_use_case=inspect_status_use_case,
    )
    operation_adapter = NucleusOperationAdapter(
        remember_use_case=remember_use_case,
        retrieve_use_case=retrieve_use_case,
        update_preview_use_case=update_preview_use_case,
        update_confirm_use_case=update_confirm_use_case,
        forget_preview_use_case=forget_preview_use_case,
        forget_confirm_use_case=forget_confirm_use_case,
        checkpoint_service=checkpoint_service,
        inspect_status_use_case=inspect_status_use_case,
        bootcard_use_case=bootcard_use_case,
        bound_profile_id=resolved_runtime_config.bound_profile_id,
        bound_workspace_id=resolved_runtime_config.bound_workspace_id,
    )

    return NucleusApp(
        remember=remember_use_case,
        retrieve=retrieve_use_case,
        update_preview=update_preview_use_case,
        update_confirm=update_confirm_use_case,
        forget_preview=forget_preview_use_case,
        forget_confirm=forget_confirm_use_case,
        checkpoint_session=checkpoint_service,
        inspect_status=inspect_status_use_case,
        bootcard=bootcard_use_case,
        mcp_server=NucleusMCPServer(operation_adapter=operation_adapter),
        http_api=NucleusHTTPAPI(operation_adapter=operation_adapter),
    )
