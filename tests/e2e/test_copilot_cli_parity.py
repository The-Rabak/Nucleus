from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from nucleus.testing.envelope_assertions import assert_mcp_tool_envelope
from nucleus.testing.sandbox import reset_sandbox


def _run_mcp_tool(*, tool: str, arguments: dict[str, object], env: dict[str, str]) -> dict[str, object]:
    process = subprocess.run(
        [
            "python3",
            "-m",
            "nucleus.adapters.mcp.server",
            "--tool",
            tool,
            "--args",
            json.dumps(arguments),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return json.loads(process.stdout)


def _run_copilot_bootstrap(*, env: dict[str, str]) -> dict[str, object]:
    process = subprocess.run(
        [
            "python3",
            "config/copilot/session_start.py",
            "--profile-id",
            "profile-alpha",
            "--workspace-id",
            "workspace-core",
            "--session-id",
            "copilot-session-1",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return json.loads(process.stdout)


def test_copilot_cli_parity_bootstrap_and_mcp_registration() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/e2e_copilot"))
    env = os.environ.copy()
    env["NUCLEUS_DATA_DIR"] = str(data_root)
    env["NUCLEUS_ENV_FILE"] = ".env"
    env["PYTHONPATH"] = "src"

    config_payload = json.loads(Path(".github/copilot-mcp-config.json").read_text(encoding="utf-8"))
    external_policy = config_payload["externalMcpPolicy"]["allowlistedServers"]
    assert "context7" in external_policy
    approval_artifact = external_policy["context7"]["approvalArtifact"]
    assert approval_artifact == ".github/external-mcp-approvals.md#context7"
    approval_path, _ = approval_artifact.split("#", 1)
    assert Path(approval_path).exists()

    nucleus_registration = config_payload["mcpServers"]["nucleus"]
    assert nucleus_registration["type"] == "stdio"
    assert nucleus_registration["envFile"] == ".env"
    serialized_registration = json.dumps(nucleus_registration)
    assert "localhost:8000" not in serialized_registration
    assert "127.0.0.1:8000" not in serialized_registration

    context7_registration = config_payload["mcpServers"]["context7"]
    assert context7_registration["approvalArtifact"] == approval_artifact

    discovered_tools_process = subprocess.run(
        ["python3", "-m", "nucleus.adapters.mcp.server", "--list-tools"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    discovered_tools = json.loads(discovered_tools_process.stdout)
    assert {"remember", "retrieve", "bootcard"}.issubset(set(discovered_tools))

    bootcard_payload = _run_copilot_bootstrap(env=env)
    assert_mcp_tool_envelope(bootcard_payload)
    assert "bootstrap" in bootcard_payload["content"][0]["text"].lower()

    remember_payload = _run_mcp_tool(
        tool="remember",
        arguments={
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "source_type": "chat_turn",
            "content": "Copilot noted that Project Apollo budget is 1200 USD.",
            "session_id": "copilot-session-1",
            "speaker": "Rabak",
            "role": "user",
        },
        env=env,
    )
    assert_mcp_tool_envelope(remember_payload)
    assert remember_payload["structuredContent"]["index_status"] == "pending"

    retrieve_payload = _run_mcp_tool(
        tool="retrieve",
        arguments={
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Apollo budget",
        },
        env=env,
    )
    assert_mcp_tool_envelope(retrieve_payload)
    retrieve_structured = retrieve_payload["structuredContent"]
    assert retrieve_structured["evidence_status"] == "found"
    assert retrieve_structured["effective_scope"] == "workspace_local"
    assert retrieve_structured["scope_widened"] is False

    _run_mcp_tool(
        tool="remember",
        arguments={
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-other",
            "source_type": "chat_turn",
            "content": "Profile-global widening exposes this cross-workspace memory.",
            "session_id": "copilot-session-1",
            "speaker": "Rabak",
            "role": "user",
        },
        env=env,
    )
    widened_payload = _run_mcp_tool(
        tool="retrieve",
        arguments={
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "cross-workspace memory",
            "scope_mode": "profile_global",
        },
        env=env,
    )
    widened_structured = widened_payload["structuredContent"]
    assert widened_structured["evidence_status"] == "found"
    assert widened_structured["effective_scope"] == "profile_global"
    assert widened_structured["scope_widened"] is True

    copilot_instructions = Path(".github/copilot-instructions.md").read_text(encoding="utf-8")
    memory_instructions = Path(".github/instructions/nucleus-memory.instructions.md").read_text(
        encoding="utf-8"
    )
    assert len(copilot_instructions.splitlines()) <= 70
    assert len(memory_instructions.splitlines()) <= 90
    assert "bootcard" in copilot_instructions
    assert "config/copilot/session_start.py" in copilot_instructions
    assert "retrieve" in copilot_instructions
    assert "checkpoint_session" in copilot_instructions
    assert "not part of the current slice 1 tool set" in copilot_instructions.lower()
    assert "not yet exposed" in memory_instructions.lower()
    assert "workspace_local" in memory_instructions
    assert "scope_mode=profile_global" in memory_instructions
    assert "dynamic runtime context" in memory_instructions.lower()
