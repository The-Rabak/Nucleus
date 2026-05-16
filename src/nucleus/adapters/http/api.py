from __future__ import annotations

import argparse
import json

from nucleus.adapters.mcp.server import NucleusOperationAdapter, STAGE1_OPERATIONS
from nucleus.domain.envelopes import HTTPOperationEnvelope, JsonObject
from nucleus.infra.runtime_config import load_runtime_config


class NucleusHTTPAPI:
    def __init__(self, *, operation_adapter: NucleusOperationAdapter) -> None:
        self._operation_adapter = operation_adapter

    def list_operations(self) -> list[str]:
        return self._operation_adapter.list_operations()

    def call_operation(self, name: str, arguments: JsonObject) -> HTTPOperationEnvelope:
        structured, text = self._operation_adapter.execute_operation(name, arguments)
        return {
            "operation": name,
            "result": structured,
            "summary": text,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-operations", action="store_true")
    parser.add_argument("--operation", choices=STAGE1_OPERATIONS)
    parser.add_argument("--args", default="{}")
    args = parser.parse_args()

    from nucleus.infra.app_factory import create_app

    runtime_config = load_runtime_config()
    app = create_app(runtime_config=runtime_config)
    if args.list_operations:
        print(json.dumps(app.http_api.list_operations()))
        return
    if not args.operation:
        parser.error("--operation is required unless --list-operations is provided.")

    payload = app.http_api.call_operation(args.operation, json.loads(args.args))
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
