from __future__ import annotations

import argparse
import json
from typing import Callable, cast

from nucleus.application.bootcard_use_case import BootcardUseCase
from nucleus.application.forget_confirm_use_case import ForgetConfirmUseCase
from nucleus.application.forget_preview_use_case import ForgetPreviewUseCase
from nucleus.application.inspect_status_use_case import InspectStatusUseCase
from nucleus.application.remember_use_case import RememberRequest, RememberUseCase
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.application.session_checkpoint_service import SessionCheckpointService
from nucleus.application.update_confirm_use_case import UpdateConfirmRequest, UpdateConfirmUseCase
from nucleus.application.update_preview_use_case import UpdatePreviewUseCase
from nucleus.domain.constants import (
    CheckpointTrigger,
    MutationOperation,
    STAGE1_OPERATION_NAMES,
    Stage1Operation,
)
from nucleus.domain.envelopes import JsonObject, MCPToolEnvelope
from nucleus.domain.scoping import resolve_scope_mode
from nucleus.infra.runtime_config import load_runtime_config

STAGE1_OPERATIONS = STAGE1_OPERATION_NAMES

OperationHandler = Callable[[JsonObject], tuple[JsonObject, str]]


class NucleusOperationAdapter:
    """Routes public Stage 1 operations to shared application use cases."""

    def __init__(
        self,
        *,
        remember_use_case: RememberUseCase,
        retrieve_use_case: RetrieveUseCase,
        update_preview_use_case: UpdatePreviewUseCase,
        update_confirm_use_case: UpdateConfirmUseCase,
        forget_preview_use_case: ForgetPreviewUseCase,
        forget_confirm_use_case: ForgetConfirmUseCase,
        checkpoint_service: SessionCheckpointService,
        inspect_status_use_case: InspectStatusUseCase,
        bootcard_use_case: BootcardUseCase,
        bound_profile_id: str | None = None,
        bound_workspace_id: str | None = None,
    ) -> None:
        self._remember_use_case = remember_use_case
        self._retrieve_use_case = retrieve_use_case
        self._update_preview_use_case = update_preview_use_case
        self._update_confirm_use_case = update_confirm_use_case
        self._forget_preview_use_case = forget_preview_use_case
        self._forget_confirm_use_case = forget_confirm_use_case
        self._checkpoint_service = checkpoint_service
        self._inspect_status_use_case = inspect_status_use_case
        self._bootcard_use_case = bootcard_use_case
        self._bound_profile_id = bound_profile_id
        self._bound_workspace_id = bound_workspace_id
        self._operation_handlers = self._build_operation_handlers()

    def _build_operation_handlers(self) -> dict[str, OperationHandler]:
        """Builds operation name -> handler mapping."""
        return {
            Stage1Operation.REMEMBER.value: self._execute_remember,
            Stage1Operation.RETRIEVE.value: self._execute_retrieve,
            Stage1Operation.UPDATE_PREVIEW.value: self._execute_update_preview,
            Stage1Operation.UPDATE_CONFIRM.value: self._execute_update_confirm,
            Stage1Operation.FORGET_PREVIEW.value: self._execute_forget_preview,
            Stage1Operation.FORGET_CONFIRM.value: self._execute_forget_confirm,
            Stage1Operation.CHECKPOINT_SESSION.value: self._execute_checkpoint_session,
            Stage1Operation.INSPECT_STATUS.value: self._execute_inspect_status,
            Stage1Operation.BOOTCARD.value: self._execute_bootcard,
        }

    def list_operations(self) -> list[str]:
        """Lists supported Stage 1 operation names."""
        return list(STAGE1_OPERATIONS)

    def execute_operation(self, name: str, arguments: JsonObject) -> tuple[JsonObject, str]:
        """Executes one operation through the registered handler map."""
        handler = self._operation_handlers.get(name)
        if handler is None:
            raise ValueError(f"Unknown MCP tool: {name}")
        return handler(arguments)

    def _execute_remember(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        result = self._remember_use_case.execute(request=self._remember_request(scoped))
        structured = result.to_dict()
        text = f"remember accepted: ingest_id={structured['ingest_id']} index_status={structured['index_status']}"
        return structured, text

    @staticmethod
    def _remember_request(scoped_arguments: JsonObject) -> RememberRequest:
        return RememberRequest(
            profile_id=cast(str, scoped_arguments["profile_id"]),
            workspace_id=cast(str, scoped_arguments["workspace_id"]),
            source_type=cast(str, scoped_arguments["source_type"]),
            content=cast(str, scoped_arguments["content"]),
            source_ref=cast(str | None, scoped_arguments.get("source_ref")),
            session_id=cast(str | None, scoped_arguments.get("session_id")),
            turn_index=cast(int | None, scoped_arguments.get("turn_index")),
            speaker=cast(str | None, scoped_arguments.get("speaker")),
            role=cast(str | None, scoped_arguments.get("role")),
            observed_at=cast(str | None, scoped_arguments.get("observed_at")),
        )

    def _execute_retrieve(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        scope = resolve_scope_mode(scope_mode=cast(str | None, scoped.get("scope_mode")))
        self._ensure_scope_allowed(scope_widened=scope.scope_widened)
        scoped["scope_mode"] = scope.requested_scope_mode
        result = self._retrieve_use_case.execute(**scoped)
        structured = result.to_dict()
        text = (
            f"retrieve {structured['evidence_status']}: "
            f"{len(structured['results'])} cited result(s) in {structured['effective_scope']} "
            f"(requested={structured['requested_scope_mode']}, policy={structured['scope_policy']})"
        )
        return structured, text

    def _execute_update_preview(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        self._require_field(
            scoped,
            field="query",
            operation=Stage1Operation.UPDATE_PREVIEW.value,
        )
        result = self._update_preview_use_case.execute(
            profile_id=cast(str, scoped["profile_id"]),
            workspace_id=cast(str, scoped["workspace_id"]),
            query=cast(str, scoped["query"]),
            top_k=cast(int, scoped.get("top_k", 5)),
            scope_mode=cast(str | None, scoped.get("scope_mode")),
        )
        structured = result.to_dict()
        text = (
            f"update_preview ready: {len(structured['candidates'])} candidate(s), "
            f"token_id={structured['token_id']} ttl={structured['ttl_seconds']}s"
        )
        return structured, text

    def _execute_update_confirm(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        self._require_field(
            scoped,
            field="preview_token",
            operation=Stage1Operation.UPDATE_CONFIRM.value,
        )
        self._require_field(
            scoped,
            field="replacement_content",
            operation=Stage1Operation.UPDATE_CONFIRM.value,
        )
        result = self._update_confirm_use_case.execute(
            request=self._update_confirm_request(scoped),
        )
        structured = result.to_dict()
        text = (
            "update_confirm applied: "
            f"superseded={structured['applied_count']} "
            f"replacement={structured['replacement_episode_id']}"
        )
        return structured, text

    def _update_confirm_request(self, scoped_arguments: JsonObject) -> UpdateConfirmRequest:
        return UpdateConfirmRequest(
            profile_id=cast(str, scoped_arguments["profile_id"]),
            workspace_id=cast(str, scoped_arguments["workspace_id"]),
            preview_token=cast(str, scoped_arguments["preview_token"]),
            selected_episode_ids=self._selected_episode_ids(scoped_arguments),
            replacement_content=cast(str, scoped_arguments["replacement_content"]),
            source_type=cast(
                str,
                scoped_arguments.get(
                    "source_type",
                    MutationOperation.UPDATE_CONFIRM.value,
                ),
            ),
            source_ref=cast(str | None, scoped_arguments.get("source_ref")),
            session_id=cast(str | None, scoped_arguments.get("session_id")),
            turn_index=cast(int | None, scoped_arguments.get("turn_index")),
            speaker=cast(str | None, scoped_arguments.get("speaker")),
            role=cast(str | None, scoped_arguments.get("role")),
            observed_at=cast(str | None, scoped_arguments.get("observed_at")),
        )

    def _execute_forget_preview(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        self._require_field(
            scoped,
            field="query",
            operation=Stage1Operation.FORGET_PREVIEW.value,
        )
        result = self._forget_preview_use_case.execute(
            profile_id=cast(str, scoped["profile_id"]),
            workspace_id=cast(str, scoped["workspace_id"]),
            query=cast(str, scoped["query"]),
            top_k=cast(int, scoped.get("top_k", 5)),
            scope_mode=cast(str | None, scoped.get("scope_mode")),
        )
        structured = result.to_dict()
        text = (
            f"forget_preview ready: {len(structured['candidates'])} candidate(s), "
            f"token_id={structured['token_id']} ttl={structured['ttl_seconds']}s"
        )
        return structured, text

    def _execute_forget_confirm(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        self._require_field(
            scoped,
            field="preview_token",
            operation=Stage1Operation.FORGET_CONFIRM.value,
        )
        result = self._forget_confirm_use_case.execute(
            profile_id=cast(str, scoped["profile_id"]),
            workspace_id=cast(str, scoped["workspace_id"]),
            preview_token=cast(str, scoped["preview_token"]),
            selected_episode_ids=self._selected_episode_ids(scoped),
        )
        structured = result.to_dict()
        text = (
            "forget_confirm applied: "
            f"forgotten={len(structured['forgotten_episode_ids'])} "
            f"event={structured['audit']['event_id']}"
        )
        return structured, text

    def _execute_checkpoint_session(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        self._require_field(
            scoped,
            field="session_id",
            operation=Stage1Operation.CHECKPOINT_SESSION.value,
        )
        self._require_field(
            scoped,
            field="idempotency_key",
            operation=Stage1Operation.CHECKPOINT_SESSION.value,
        )
        result = self._checkpoint_service.execute(
            profile_id=cast(str, scoped["profile_id"]),
            workspace_id=cast(str, scoped["workspace_id"]),
            session_id=cast(str, scoped["session_id"]),
            trigger=cast(str, scoped.get("trigger", CheckpointTrigger.MANUAL.value)),
            idempotency_key=cast(str, scoped["idempotency_key"]),
            include_preview_tokens=cast(bool, scoped.get("include_preview_tokens", True)),
        )
        structured = result.to_dict()
        text = (
            f"checkpoint_session {structured['trigger']}: "
            f"checkpoint_id={structured['checkpoint_id']} "
            f"idempotent={structured['idempotent']}"
        )
        return structured, text

    def _execute_inspect_status(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        self._require_field(
            scoped,
            field="session_id",
            operation=Stage1Operation.INSPECT_STATUS.value,
        )
        result = self._inspect_status_use_case.execute(
            profile_id=cast(str, scoped["profile_id"]),
            workspace_id=cast(str, scoped["workspace_id"]),
            session_id=cast(str, scoped["session_id"]),
        )
        structured = result.to_dict()
        checkpoint = structured.get("latest_checkpoint")
        checkpoint_id = self._checkpoint_id_text(checkpoint)
        text = f"inspect_status ({structured['effective_scope']}): latest_checkpoint={checkpoint_id}"
        return structured, text

    def _execute_bootcard(self, arguments: JsonObject) -> tuple[JsonObject, str]:
        scoped = self._scoped_arguments(arguments)
        result = self._bootcard_use_case.execute(**scoped)
        structured = result.to_dict()
        text = (
            f"bootstrap ready for workspace {scoped['workspace_id']} "
            f"(scope={structured['effective_scope']}, readiness={structured['readiness']['index_status']})"
        )
        return structured, text

    def _scoped_arguments(self, arguments: JsonObject) -> JsonObject:
        if "profile_id" not in arguments or "workspace_id" not in arguments:
            raise ValueError("profile_id and workspace_id are required.")
        scoped_arguments = dict(arguments)
        scoped_arguments["profile_id"] = validate_scope_identifier(
            name="profile_id",
            value=scoped_arguments["profile_id"],
        )
        scoped_arguments["workspace_id"] = validate_scope_identifier(
            name="workspace_id",
            value=scoped_arguments["workspace_id"],
        )
        self._enforce_bound_scope(scoped_arguments)
        return scoped_arguments

    def _enforce_bound_scope(self, scoped_arguments: JsonObject) -> None:
        if self._bound_profile_id and scoped_arguments["profile_id"] != self._bound_profile_id:
            raise ValueError("profile_id is outside the configured server scope.")
        if self._bound_workspace_id and scoped_arguments["workspace_id"] != self._bound_workspace_id:
            raise ValueError("workspace_id is outside the configured server scope.")

    def _ensure_scope_allowed(self, *, scope_widened: bool) -> None:
        if scope_widened and self._bound_workspace_id is not None:
            raise ValueError("profile_global scope_mode is outside the configured server scope.")

    @staticmethod
    def _require_field(arguments: JsonObject, *, field: str, operation: str) -> None:
        if field not in arguments:
            raise ValueError(f"{field} is required for {operation}.")

    @staticmethod
    def _selected_episode_ids(arguments: JsonObject) -> list[str]:
        if "selected_episode_ids" not in arguments:
            raise ValueError("selected_episode_ids is required.")
        raw = arguments["selected_episode_ids"]
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ValueError("selected_episode_ids must be a list of strings.")
        return cast(list[str], raw)

    @staticmethod
    def _checkpoint_id_text(checkpoint: object) -> object:
        if not isinstance(checkpoint, dict):
            return "none"
        return cast(dict[str, object], checkpoint).get("checkpoint_id")


class NucleusMCPServer:
    """MCP-friendly envelope adapter over `NucleusOperationAdapter`."""

    def __init__(self, *, operation_adapter: NucleusOperationAdapter) -> None:
        self._operation_adapter = operation_adapter

    def list_tools(self) -> list[str]:
        return self._operation_adapter.list_operations()

    def call_tool(self, name: str, arguments: JsonObject) -> MCPToolEnvelope:
        structured, text = self._operation_adapter.execute_operation(name, arguments)
        return self._envelope(structured=structured, text=text)

    @staticmethod
    def _envelope(*, structured: JsonObject, text: str) -> MCPToolEnvelope:
        return {
            "structuredContent": structured,
            "content": [{"type": "text", "text": text}],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--tool", choices=STAGE1_OPERATIONS)
    parser.add_argument("--args", default="{}")
    args = parser.parse_args()

    from nucleus.infra.app_factory import create_app

    runtime_config = load_runtime_config()
    app = create_app(runtime_config=runtime_config)
    if args.list_tools:
        print(json.dumps(app.mcp_server.list_tools()))
        return
    if not args.tool:
        parser.error("--tool is required unless --list-tools is provided.")

    payload = app.mcp_server.call_tool(args.tool, json.loads(args.args))
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
