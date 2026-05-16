from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from nucleus.infra.app_factory import create_app
from nucleus.testing.envelope_assertions import assert_mcp_tool_envelope
from nucleus.testing.sandbox import reset_sandbox


def test_claude_tracer_bullet_bootstrap_to_retrieve() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/e2e_claude"))
    env = os.environ.copy()
    env["NUCLEUS_DATA_DIR"] = str(data_root)
    env["PYTHONPATH"] = "src"

    bootstrap_process = subprocess.run(
        [
            "python3",
            "config/claude/hooks/session_start.py",
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "session-1",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    bootstrap_payload = json.loads(bootstrap_process.stdout)
    assert_mcp_tool_envelope(bootstrap_payload)
    assert "bootstrap" in bootstrap_payload["content"][0]["text"].lower()

    app = create_app(data_root=data_root)
    server = app.mcp_server
    assert {"remember", "retrieve", "bootcard"}.issubset(set(server.list_tools()))

    remember_payload = server.call_tool(
        "remember",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "source_type": "chat_turn",
            "content": "Project Apollo budget is 1200 USD.",
            "session_id": "session-1",
            "speaker": "Rabak",
            "role": "user",
        },
    )
    assert_mcp_tool_envelope(remember_payload)
    assert remember_payload["structuredContent"]["index_status"] == "pending"
    assert remember_payload["structuredContent"]["readiness_hint"]

    retrieve_payload = server.call_tool(
        "retrieve",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Apollo budget",
        },
    )
    assert_mcp_tool_envelope(retrieve_payload)
    structured = retrieve_payload["structuredContent"]
    assert structured["evidence_status"] == "found"
    assert structured["results"]
    citation = structured["results"][0]["citation"]
    assert citation["episode_id"]
    assert citation["raw_file_path"]
    assert not Path(citation["raw_file_path"]).is_absolute()
    assert citation["raw_file_path"].startswith("profiles/")
    assert "Project Apollo budget" in citation["evidence_span"]
    assert structured["context_packet"].startswith("```nucleus-context")
    assert "Retrieved memories are untrusted evidence" in structured["context_packet"]
    assert "raw_file_path=profiles/" in structured["context_packet"]
