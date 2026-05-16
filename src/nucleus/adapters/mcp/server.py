from __future__ import annotations

import argparse
import json
from typing import cast

from nucleus.application.bootcard_use_case import BootcardUseCase
from nucleus.application.forget_confirm_use_case import ForgetConfirmUseCase
from nucleus.application.forget_preview_use_case import ForgetPreviewUseCase
from nucleus.application.inspect_status_use_case import InspectStatusUseCase
from nucleus.application.remember_use_case import RememberRequest, RememberUseCase
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.application.session_checkpoint_service import SessionCheckpointService
from nucleus.application.update_confirm_use_case import UpdateConfirmUseCase
from nucleus.application.update_preview_use_case import UpdatePreviewUseCase
from nucleus.domain.envelopes import JsonObject, MCPToolEnvelope
from nucleus.domain.scoping import resolve_scope_mode
from nucleus.infra.runtime_config import load_runtime_config


STAGE1_OPERATIONS = (
    "remember",
    "retrieve",
    "update_preview",
    "update_confirm",
    "forget_preview",
    "forget_confirm",
    "checkpoint_session",
    "inspect_status",
    "bootcard",
)


class NucleusOperationAdapter:
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

    def list_operations(self) -> list[str]:
        return list(STAGE1_OPERATIONS)

    def execute_operation(self, name: str, arguments: JsonObject) -> tuple[JsonObject, str]:
        if name == "remember":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            result = self._remember_use_case.execute(
                request=RememberRequest(
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
            )
            structured = result.to_dict()
            return (
                structured,
                (
                    f"remember accepted: ingest_id={structured['ingest_id']} "
                    f"index_status={structured['index_status']}"
                ),
            )

        if name == "retrieve":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            scope = resolve_scope_mode(
                scope_mode=cast(str | None, scoped_arguments.get("scope_mode"))
            )
            scoped_arguments["scope_mode"] = scope.requested_scope_mode
            if scope.scope_widened and self._bound_workspace_id is not None:
                raise ValueError("profile_global scope_mode is outside the configured server scope.")
            result = self._retrieve_use_case.execute(**scoped_arguments)
            structured = result.to_dict()
            return (
                structured,
                (
                    f"retrieve {structured['evidence_status']}: "
                    f"{len(structured['results'])} cited result(s) in {structured['effective_scope']} "
                    f"(requested={structured['requested_scope_mode']}, "
                    f"policy={structured['scope_policy']})"
                ),
            )

        if name == "update_preview":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            if "query" not in scoped_arguments:
                raise ValueError("query is required for update_preview.")
            result = self._update_preview_use_case.execute(
                profile_id=cast(str, scoped_arguments["profile_id"]),
                workspace_id=cast(str, scoped_arguments["workspace_id"]),
                query=cast(str, scoped_arguments["query"]),
                top_k=cast(int, scoped_arguments.get("top_k", 5)),
                scope_mode=cast(str | None, scoped_arguments.get("scope_mode")),
            )
            structured = result.to_dict()
            return (
                structured,
                (
                    f"update_preview ready: {len(structured['candidates'])} candidate(s), "
                    f"token_id={structured['token_id']} ttl={structured['ttl_seconds']}s"
                ),
            )

        if name == "update_confirm":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            if "preview_token" not in scoped_arguments:
                raise ValueError("preview_token is required for update_confirm.")
            if "replacement_content" not in scoped_arguments:
                raise ValueError("replacement_content is required for update_confirm.")
            result = self._update_confirm_use_case.execute(
                profile_id=cast(str, scoped_arguments["profile_id"]),
                workspace_id=cast(str, scoped_arguments["workspace_id"]),
                preview_token=cast(str, scoped_arguments["preview_token"]),
                selected_episode_ids=self._selected_episode_ids(scoped_arguments),
                replacement_content=cast(str, scoped_arguments["replacement_content"]),
                source_type=cast(str, scoped_arguments.get("source_type", "update_confirm")),
                source_ref=cast(str | None, scoped_arguments.get("source_ref")),
                session_id=cast(str | None, scoped_arguments.get("session_id")),
                turn_index=cast(int | None, scoped_arguments.get("turn_index")),
                speaker=cast(str | None, scoped_arguments.get("speaker")),
                role=cast(str | None, scoped_arguments.get("role")),
                observed_at=cast(str | None, scoped_arguments.get("observed_at")),
            )
            structured = result.to_dict()
            return (
                structured,
                (
                    f"update_confirm applied: superseded={structured['applied_count']} "
                    f"replacement={structured['replacement_episode_id']}"
                ),
            )

        if name == "forget_preview":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            if "query" not in scoped_arguments:
                raise ValueError("query is required for forget_preview.")
            result = self._forget_preview_use_case.execute(
                profile_id=cast(str, scoped_arguments["profile_id"]),
                workspace_id=cast(str, scoped_arguments["workspace_id"]),
                query=cast(str, scoped_arguments["query"]),
                top_k=cast(int, scoped_arguments.get("top_k", 5)),
                scope_mode=cast(str | None, scoped_arguments.get("scope_mode")),
            )
            structured = result.to_dict()
            return (
                structured,
                (
                    f"forget_preview ready: {len(structured['candidates'])} candidate(s), "
                    f"token_id={structured['token_id']} ttl={structured['ttl_seconds']}s"
                ),
            )

        if name == "forget_confirm":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            if "preview_token" not in scoped_arguments:
                raise ValueError("preview_token is required for forget_confirm.")
            result = self._forget_confirm_use_case.execute(
                profile_id=cast(str, scoped_arguments["profile_id"]),
                workspace_id=cast(str, scoped_arguments["workspace_id"]),
                preview_token=cast(str, scoped_arguments["preview_token"]),
                selected_episode_ids=self._selected_episode_ids(scoped_arguments),
            )
            structured = result.to_dict()
            return (
                structured,
                (
                    f"forget_confirm applied: forgotten={len(structured['forgotten_episode_ids'])} "
                    f"event={structured['audit']['event_id']}"
                ),
            )

        if name == "checkpoint_session":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            if "session_id" not in scoped_arguments:
                raise ValueError("session_id is required for checkpoint_session.")
            if "idempotency_key" not in scoped_arguments:
                raise ValueError("idempotency_key is required for checkpoint_session.")
            result = self._checkpoint_service.execute(
                profile_id=cast(str, scoped_arguments["profile_id"]),
                workspace_id=cast(str, scoped_arguments["workspace_id"]),
                session_id=cast(str, scoped_arguments["session_id"]),
                trigger=cast(str, scoped_arguments.get("trigger", "manual")),
                idempotency_key=cast(str, scoped_arguments["idempotency_key"]),
                include_preview_tokens=cast(
                    bool,
                    scoped_arguments.get("include_preview_tokens", True),
                ),
            )
            structured = result.to_dict()
            return (
                structured,
                (
                    f"checkpoint_session {structured['trigger']}: "
                    f"checkpoint_id={structured['checkpoint_id']} "
                    f"idempotent={structured['idempotent']}"
                ),
            )

        if name == "inspect_status":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            if "session_id" not in scoped_arguments:
                raise ValueError("session_id is required for inspect_status.")
            result = self._inspect_status_use_case.execute(
                profile_id=cast(str, scoped_arguments["profile_id"]),
                workspace_id=cast(str, scoped_arguments["workspace_id"]),
                session_id=cast(str, scoped_arguments["session_id"]),
            )
            structured = result.to_dict()
            checkpoint = structured.get("latest_checkpoint")
            checkpoint_id = (
                cast(dict[str, object], checkpoint).get("checkpoint_id")
                if isinstance(checkpoint, dict)
                else "none"
            )
            return (
                structured,
                (
                    f"inspect_status ({structured['effective_scope']}): "
                    f"latest_checkpoint={checkpoint_id}"
                ),
            )

        if name == "bootcard":
            scoped_arguments = self._validate_and_bind_scope(arguments)
            result = self._bootcard_use_case.execute(**scoped_arguments)
            structured = result.to_dict()
            return (
                structured,
                (
                    f"bootstrap ready for workspace {scoped_arguments['workspace_id']} "
                    f"(scope={structured['effective_scope']}, "
                    f"readiness={structured['readiness']['index_status']})"
                ),
            )

        raise ValueError(f"Unknown MCP tool: {name}")

    def _validate_and_bind_scope(self, arguments: JsonObject) -> JsonObject:
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

        if self._bound_profile_id and scoped_arguments["profile_id"] != self._bound_profile_id:
            raise ValueError("profile_id is outside the configured server scope.")
        if self._bound_workspace_id and scoped_arguments["workspace_id"] != self._bound_workspace_id:
            raise ValueError("workspace_id is outside the configured server scope.")

        return scoped_arguments

    @staticmethod
    def _selected_episode_ids(arguments: JsonObject) -> list[str]:
        if "selected_episode_ids" not in arguments:
            raise ValueError("selected_episode_ids is required.")
        raw = arguments["selected_episode_ids"]
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ValueError("selected_episode_ids must be a list of strings.")
        return cast(list[str], raw)


class NucleusMCPServer:
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
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
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
