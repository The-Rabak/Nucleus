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


@dataclass(slots=True)
class NucleusUseCases:
    remember: RememberUseCase
    retrieve: RetrieveUseCase
    update_preview: UpdatePreviewUseCase
    update_confirm: UpdateConfirmUseCase
    forget_preview: ForgetPreviewUseCase
    forget_confirm: ForgetConfirmUseCase
    checkpoint_session: SessionCheckpointService
    inspect_status: InspectStatusUseCase
    bootcard: BootcardUseCase


def create_app(
    *,
    data_root: Path | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> NucleusApp:
    """Builds the production app container and all operation adapters."""
    resolved_runtime_config = runtime_config or load_runtime_config(data_root=data_root)
    use_cases = _build_use_cases(data_dir=resolved_runtime_config.data_dir)
    operation_adapter = NucleusOperationAdapter(
        remember_use_case=use_cases.remember,
        retrieve_use_case=use_cases.retrieve,
        update_preview_use_case=use_cases.update_preview,
        update_confirm_use_case=use_cases.update_confirm,
        forget_preview_use_case=use_cases.forget_preview,
        forget_confirm_use_case=use_cases.forget_confirm,
        checkpoint_service=use_cases.checkpoint_session,
        inspect_status_use_case=use_cases.inspect_status,
        bootcard_use_case=use_cases.bootcard,
        bound_profile_id=resolved_runtime_config.bound_profile_id,
        bound_workspace_id=resolved_runtime_config.bound_workspace_id,
        require_bound_scope=resolved_runtime_config.require_bound_scope,
    )
    return _build_nucleus_app(use_cases=use_cases, operation_adapter=operation_adapter)


def _build_use_cases(*, data_dir: Path) -> NucleusUseCases:
    """Builds all application-layer use cases from shared dependencies."""
    episode_store = EpisodeStore(data_root=data_dir)
    readiness_store = ReadinessStore(data_root=data_dir)
    remember = RememberUseCase(episode_store=episode_store, readiness_store=readiness_store)
    retrieve = RetrieveUseCase(episode_store=episode_store, readiness_store=readiness_store)
    mutation_use_cases = _build_mutation_use_cases(
        episode_store=episode_store,
        remember=remember,
        retrieve=retrieve,
    )
    status_use_cases = _build_status_use_cases(
        episode_store=episode_store,
        readiness_store=readiness_store,
        data_dir=data_dir,
    )
    return _assemble_use_cases(
        remember=remember,
        retrieve=retrieve,
        mutation_use_cases=mutation_use_cases,
        status_use_cases=status_use_cases,
    )


def _assemble_use_cases(
    *,
    remember: RememberUseCase,
    retrieve: RetrieveUseCase,
    mutation_use_cases: tuple[UpdatePreviewUseCase, UpdateConfirmUseCase, ForgetPreviewUseCase, ForgetConfirmUseCase],
    status_use_cases: tuple[SessionCheckpointService, InspectStatusUseCase, BootcardUseCase],
) -> NucleusUseCases:
    update_preview, update_confirm, forget_preview, forget_confirm = mutation_use_cases
    checkpoint_session, inspect_status, bootcard = status_use_cases
    return NucleusUseCases(
        remember=remember,
        retrieve=retrieve,
        update_preview=update_preview,
        update_confirm=update_confirm,
        forget_preview=forget_preview,
        forget_confirm=forget_confirm,
        checkpoint_session=checkpoint_session,
        inspect_status=inspect_status,
        bootcard=bootcard,
    )


def _build_status_use_cases(
    *,
    episode_store: EpisodeStore,
    readiness_store: ReadinessStore,
    data_dir: Path,
) -> tuple[SessionCheckpointService, InspectStatusUseCase, BootcardUseCase]:
    checkpoint_session = _build_checkpoint_service(
        episode_store=episode_store,
        readiness_store=readiness_store,
        data_dir=data_dir,
    )
    inspect_status = InspectStatusUseCase(
        readiness_store=readiness_store,
        checkpoint_service=checkpoint_session,
    )
    bootcard = BootcardUseCase(
        episode_store=episode_store,
        readiness_store=readiness_store,
        inspect_status_use_case=inspect_status,
    )
    return checkpoint_session, inspect_status, bootcard


def _build_mutation_use_cases(
    *,
    episode_store: EpisodeStore,
    remember: RememberUseCase,
    retrieve: RetrieveUseCase,
) -> tuple[UpdatePreviewUseCase, UpdateConfirmUseCase, ForgetPreviewUseCase, ForgetConfirmUseCase]:
    update_preview = UpdatePreviewUseCase(retrieve_use_case=retrieve, episode_store=episode_store)
    update_confirm = UpdateConfirmUseCase(episode_store=episode_store, remember_use_case=remember)
    forget_preview = ForgetPreviewUseCase(retrieve_use_case=retrieve, episode_store=episode_store)
    forget_confirm = ForgetConfirmUseCase(episode_store=episode_store)
    return update_preview, update_confirm, forget_preview, forget_confirm


def _build_checkpoint_service(
    *,
    episode_store: EpisodeStore,
    readiness_store: ReadinessStore,
    data_dir: Path,
) -> SessionCheckpointService:
    return SessionCheckpointService(
        episode_store=episode_store,
        readiness_store=readiness_store,
        data_root=data_dir,
    )


def _build_nucleus_app(
    *,
    use_cases: NucleusUseCases,
    operation_adapter: NucleusOperationAdapter,
) -> NucleusApp:
    """Builds the public app container returned by `create_app`."""
    return NucleusApp(
        remember=use_cases.remember,
        retrieve=use_cases.retrieve,
        update_preview=use_cases.update_preview,
        update_confirm=use_cases.update_confirm,
        forget_preview=use_cases.forget_preview,
        forget_confirm=use_cases.forget_confirm,
        checkpoint_session=use_cases.checkpoint_session,
        inspect_status=use_cases.inspect_status,
        bootcard=use_cases.bootcard,
        mcp_server=NucleusMCPServer(operation_adapter=operation_adapter),
        http_api=NucleusHTTPAPI(operation_adapter=operation_adapter),
    )
