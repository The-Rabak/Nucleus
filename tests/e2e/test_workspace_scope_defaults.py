from __future__ import annotations

from pathlib import Path

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_workspace_scope_defaults_and_non_sticky_widening() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/e2e_workspace_scope_defaults"))
    app = create_app(data_root=data_root)

    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Core workspace note: only local priorities are tracked here.",
        session_id="session-22",
    )
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-other",
        source_type="chat_turn",
        content="ORBIT_ONLY_SIGNAL is tracked in workspace other.",
        session_id="session-22",
    )
    app.remember.execute_from_fields(
        profile_id="profile-beta",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="NEBULA_ONLY_SIGNAL is tracked in another profile.",
        session_id="session-22",
    )

    local_payload = app.mcp_server.call_tool(
        "retrieve",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "ORBIT_ONLY_SIGNAL",
        },
    )
    local_structured = local_payload["structuredContent"]
    assert local_structured["evidence_status"] == "none"
    assert local_structured["effective_scope"] == "workspace_local"
    assert local_structured["requested_scope_mode"] == "workspace_local"
    assert local_structured["scope_widened"] is False
    assert local_structured["scope_policy"] == "per_request_non_sticky"
    assert "workspace_local" in local_payload["content"][0]["text"]

    widened_payload = app.mcp_server.call_tool(
        "retrieve",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "ORBIT_ONLY_SIGNAL",
            "scope_mode": "profile_global",
        },
    )
    widened_structured = widened_payload["structuredContent"]
    assert widened_structured["evidence_status"] == "found"
    assert widened_structured["effective_scope"] == "profile_global"
    assert widened_structured["requested_scope_mode"] == "profile_global"
    assert widened_structured["scope_widened"] is True
    assert widened_structured["scope_policy"] == "per_request_non_sticky"
    assert any(
        "workspace-other" in result["citation"]["raw_file_path"]
        for result in widened_structured["results"]
    )
    assert all(
        "profile-beta" not in result["citation"]["raw_file_path"]
        for result in widened_structured["results"]
    )
    assert "profile_global" in widened_payload["content"][0]["text"]

    local_again_payload = app.mcp_server.call_tool(
        "retrieve",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "ORBIT_ONLY_SIGNAL",
        },
    )
    local_again_structured = local_again_payload["structuredContent"]
    assert local_again_structured["evidence_status"] == "none"
    assert local_again_structured["effective_scope"] == "workspace_local"
    assert local_again_structured["scope_widened"] is False

    bootcard_payload = app.mcp_server.call_tool(
        "bootcard",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "session_id": "session-22",
        },
    )
    bootcard_structured = bootcard_payload["structuredContent"]
    assert bootcard_structured["effective_scope"] == "workspace_local"
    assert bootcard_structured["scope_widened"] is False
    assert bootcard_structured["scope_policy"] == "per_request_non_sticky"
    assert "widening_policy" in bootcard_structured["markdown"]
    assert "non_sticky" in bootcard_structured["markdown"]
    assert "workspace_local" in bootcard_payload["content"][0]["text"]

    inspect_payload = app.mcp_server.call_tool(
        "inspect_status",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "session_id": "session-22",
        },
    )
    inspect_structured = inspect_payload["structuredContent"]
    assert inspect_structured["effective_scope"] == "workspace_local"
    assert inspect_structured["scope_widened"] is False
    assert inspect_structured["scope_policy"] == "per_request_non_sticky"
    assert "workspace_local" in inspect_payload["content"][0]["text"]
