from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from nucleus.infra.app_factory import create_app
from nucleus.testing.envelope_assertions import assert_mcp_tool_envelope
from nucleus.testing.sandbox import reset_sandbox


def _run_hook(script: str, args: list[str], env: dict[str, str]) -> dict[str, object]:
    process = subprocess.run(
        ["python3", f"config/claude/hooks/{script}", *args],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return json.loads(process.stdout)


def test_precompact_stop_checkpointing_survives_to_next_bootstrap() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/e2e_precompact_checkpointing"))
    env = os.environ.copy()
    env["NUCLEUS_DATA_DIR"] = str(data_root)
    env["PYTHONPATH"] = "src"
    discovered_tools = json.loads(
        subprocess.run(
            ["python3", "-m", "nucleus.adapters.mcp.server", "--list-tools"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=True,
            env=env,
        ).stdout
    )
    assert "checkpoint_session" in discovered_tools
    assert "inspect_status" in discovered_tools

    app = create_app(data_root=data_root)
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Durability fact: keep this across compaction.",
        session_id="session-7",
        speaker="Rabak",
        role="user",
    )

    precompact = _run_hook(
        "pre_compact.py",
        [
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "session-7",
            "--idempotency-key",
            "precompact-evt-1",
        ],
        env,
    )
    assert_mcp_tool_envelope(precompact)
    precompact_structured = precompact["structuredContent"]
    assert precompact_structured["trigger"] == "pre_compact"

    replay_precompact = _run_hook(
        "pre_compact.py",
        [
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "session-7",
            "--idempotency-key",
            "precompact-evt-1",
        ],
        env,
    )
    assert (
        replay_precompact["structuredContent"]["checkpoint_id"]
        == precompact_structured["checkpoint_id"]
    )

    stop_payload = _run_hook(
        "stop.py",
        [
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "session-7",
            "--idempotency-key",
            "stop-evt-1",
        ],
        env,
    )
    assert_mcp_tool_envelope(stop_payload)
    stop_structured = stop_payload["structuredContent"]
    assert stop_structured["trigger"] == "stop"

    session_end = _run_hook(
        "session_end.py",
        [
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "session-7",
        ],
        env,
    )
    assert_mcp_tool_envelope(session_end)
    assert session_end["structuredContent"]["cleanup_only"] is True

    manual_checkpoint = app.mcp_server.call_tool(
        "checkpoint_session",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "session_id": "session-7",
            "trigger": "manual",
            "idempotency_key": "manual-copilot-1",
        },
    )
    assert_mcp_tool_envelope(manual_checkpoint)
    assert manual_checkpoint["structuredContent"]["trigger"] == "manual"

    inspect_payload = app.mcp_server.call_tool(
        "inspect_status",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "session_id": "session-7",
        },
    )
    assert_mcp_tool_envelope(inspect_payload)
    latest_checkpoint = inspect_payload["structuredContent"]["latest_checkpoint"]
    assert latest_checkpoint is not None
    assert latest_checkpoint["trigger"] == "manual"

    bootstrap_process = subprocess.run(
        [
            "python3",
            "config/claude/hooks/session_start.py",
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "session-7",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    bootcard_payload = json.loads(bootstrap_process.stdout)
    assert_mcp_tool_envelope(bootcard_payload)
    markdown = bootcard_payload["structuredContent"]["markdown"]
    assert "Latest checkpoint" in markdown
    assert latest_checkpoint["checkpoint_id"] in markdown
