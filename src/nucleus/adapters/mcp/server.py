from __future__ import annotations

import argparse
import json
from typing import cast

from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.application.bootcard_use_case import BootcardUseCase
from nucleus.application.remember_use_case import RememberRequest, RememberUseCase
from nucleus.application.retrieve_use_case import RetrieveUseCase
from nucleus.domain.envelopes import JsonObject, MCPToolEnvelope
from nucleus.infra.runtime_config import load_runtime_config


STAGE1_OPERATIONS = ("remember", "retrieve", "bootcard")


class NucleusOperationAdapter:
    def __init__(
        self,
        *,
        remember_use_case: RememberUseCase,
        retrieve_use_case: RetrieveUseCase,
        bootcard_use_case: BootcardUseCase,
        bound_profile_id: str | None = None,
        bound_workspace_id: str | None = None,
    ) -> None:
        self._remember_use_case = remember_use_case
        self._retrieve_use_case = retrieve_use_case
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
            if (
                scoped_arguments.get("scope_mode") == "profile_global"
                and self._bound_workspace_id is not None
            ):
                raise ValueError("profile_global scope_mode is outside the configured server scope.")
            result = self._retrieve_use_case.execute(**scoped_arguments)
            structured = result.to_dict()
            return (
                structured,
                (
                    f"retrieve {structured['evidence_status']}: "
                    f"{len(structured['results'])} cited result(s) in {structured['effective_scope']}"
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
                    f"(readiness={structured['readiness']['index_status']})"
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
