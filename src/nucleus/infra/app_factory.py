from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nucleus.adapters.filesystem.episode_store import EpisodeStore
from nucleus.adapters.http.api import NucleusHTTPAPI
from nucleus.adapters.mcp.server import NucleusMCPServer, NucleusOperationAdapter
from nucleus.application.bootcard_use_case import BootcardUseCase
from nucleus.application.readiness_store import ReadinessStore
from nucleus.application.remember_use_case import RememberUseCase
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.infra.runtime_config import RuntimeConfig, load_runtime_config


@dataclass(slots=True)
class NucleusApp:
    remember: RememberUseCase
    retrieve: RetrieveUseCase
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
    bootcard_use_case = BootcardUseCase(
        episode_store=episode_store,
        readiness_store=readiness_store,
    )
    operation_adapter = NucleusOperationAdapter(
        remember_use_case=remember_use_case,
        retrieve_use_case=retrieve_use_case,
        bootcard_use_case=bootcard_use_case,
        bound_profile_id=resolved_runtime_config.bound_profile_id,
        bound_workspace_id=resolved_runtime_config.bound_workspace_id,
    )

    return NucleusApp(
        remember=remember_use_case,
        retrieve=retrieve_use_case,
        bootcard=bootcard_use_case,
        mcp_server=NucleusMCPServer(operation_adapter=operation_adapter),
        http_api=NucleusHTTPAPI(operation_adapter=operation_adapter),
    )
