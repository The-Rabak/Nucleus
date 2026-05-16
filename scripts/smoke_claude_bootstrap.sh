#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SMOKE_DIR="tests/.sandbox/smoke"
rm -rf "$SMOKE_DIR"
mkdir -p "$SMOKE_DIR"

if [[ ! -x "config/claude/hooks/session_start.py" ]]; then
  echo "Hook script missing or not executable"
  exit 1
fi

BOOTSTRAP_JSON="$(NUCLEUS_DATA_DIR="$SMOKE_DIR" python3 config/claude/hooks/session_start.py \
  --profile-id profile-smoke \
  --workspace-id workspace-smoke \
  --session-id session-smoke)"

BOOTSTRAP_JSON="$BOOTSTRAP_JSON" python3 - <<'PY'
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, "src")
from nucleus.infra.app_factory import create_app

bootstrap_payload = json.loads(os.environ["BOOTSTRAP_JSON"])
if "structuredContent" not in bootstrap_payload or "content" not in bootstrap_payload:
    raise SystemExit("Bootstrap payload missing MCP envelope")

app = create_app(data_root=Path("tests/.sandbox/smoke"))
if not {"remember", "retrieve", "bootcard"}.issubset(set(app.mcp_server.list_tools())):
    raise SystemExit("Missing required MCP tools")

remember_payload = app.mcp_server.call_tool(
    "remember",
    {
        "profile_id": "profile-smoke",
        "workspace_id": "workspace-smoke",
        "source_type": "chat_turn",
        "content": "Smoke test memory: Apollo budget is 1200 USD.",
        "session_id": "session-smoke",
        "speaker": "Rabak",
        "role": "user",
    },
)
if remember_payload["structuredContent"]["index_status"] != "pending":
    raise SystemExit("Remember readiness contract violated")

retrieve_payload = app.mcp_server.call_tool(
    "retrieve",
    {
        "profile_id": "profile-smoke",
        "workspace_id": "workspace-smoke",
        "query": "Apollo budget",
    },
)
if retrieve_payload["structuredContent"]["evidence_status"] != "found":
    raise SystemExit("Retrieve did not return cited evidence")

print("Smoke check passed: hook + MCP + bootstrap/remember/retrieve path works.")
PY
