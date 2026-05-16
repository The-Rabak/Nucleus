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


def _error_payload(error: ValueError | OSError) -> dict[str, str]:
    return {
        "kind": error.__class__.__name__,
        "message": str(error),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()

    runtime_config = load_runtime_config()
    app = create_app(runtime_config=runtime_config)

    structured = {
        "cleanup_only": True,
        "status": "ok",
        "latest_checkpoint": None,
        "readiness": None,
        "warnings": [],
    }
    summary = "session_end cleanup complete; durability is handled by pre_compact and stop checkpoints."
    try:
        status_payload = app.mcp_server.call_tool(
            "inspect_status",
            {
                "profile_id": args.profile_id,
                "workspace_id": args.workspace_id,
                "session_id": args.session_id,
            },
        )
        structured_content = status_payload["structuredContent"]
        structured["latest_checkpoint"] = structured_content.get("latest_checkpoint")
        structured["readiness"] = structured_content.get("readiness")
        structured["warnings"] = structured_content.get("warnings", [])
        if structured["warnings"]:
            structured["status"] = "degraded"
            summary = (
                "session_end cleanup degraded: inspect_status reported state warnings; "
                f"first_warning={structured['warnings'][0]}"
            )
    except (ValueError, OSError) as error:
        structured["status"] = "degraded"
        structured["error"] = _error_payload(error)
        summary = (
            "session_end cleanup degraded: inspect_status failed; "
            f"{error.__class__.__name__}: {error}"
        )

    payload = {
        "structuredContent": structured,
        "content": [
            {
                "type": "text",
                "text": summary,
            }
        ],
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
