#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from nucleus.infra.app_factory import create_app
from nucleus.infra.runtime_config import load_runtime_config


def run_checkpoint_hook(*, trigger: str) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--idempotency-key", required=True)
    args = parser.parse_args()

    runtime_config = load_runtime_config()
    app = create_app(runtime_config=runtime_config)
    payload = app.mcp_server.call_tool(
        "checkpoint_session",
        {
            "profile_id": args.profile_id,
            "workspace_id": args.workspace_id,
            "session_id": args.session_id,
            "trigger": trigger,
            "idempotency_key": args.idempotency_key,
        },
    )
    print(json.dumps(payload))
