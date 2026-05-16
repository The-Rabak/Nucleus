from __future__ import annotations

from pathlib import Path

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_http_and_mcp_share_operation_semantics() -> None:
    mcp_data_root = reset_sandbox(Path("tests/.sandbox/contract_http_mcp_mcp"))
    http_data_root = reset_sandbox(Path("tests/.sandbox/contract_http_mcp_http"))
    mcp_app = create_app(data_root=mcp_data_root)
    http_app = create_app(data_root=http_data_root)

    for app in (mcp_app, http_app):
        app.remember.execute_from_fields(
            profile_id="profile-alpha",
            workspace_id="workspace-core",
            source_type="chat_turn",
            content="Shared adapter parity should preserve retrieval scope.",
            session_id="session-1",
            speaker="Rabak",
            role="user",
        )
        app.remember.execute_from_fields(
            profile_id="profile-alpha",
            workspace_id="workspace-other",
            source_type="chat_turn",
            content="Cross-workspace parity evidence should require explicit widening.",
            session_id="session-1",
            speaker="Rabak",
            role="user",
        )

    assert set(mcp_app.mcp_server.list_tools()) == set(http_app.http_api.list_operations())

    bootcard_arguments = {
        "profile_id": "profile-alpha",
        "workspace_id": "workspace-core",
        "session_id": "session-1",
    }
    mcp_bootcard = mcp_app.mcp_server.call_tool("bootcard", bootcard_arguments)["structuredContent"]
    http_bootcard = http_app.http_api.call_operation("bootcard", bootcard_arguments)["result"]
    assert mcp_bootcard["readiness"]["index_status"] == http_bootcard["readiness"]["index_status"] == "pending"
    assert mcp_bootcard["readiness"]["truthful"] is True
    assert http_bootcard["readiness"]["truthful"] is True
    assert "workspace_local" in mcp_bootcard["markdown"]
    assert "workspace_local" in http_bootcard["markdown"]

    remember_arguments = {
        "profile_id": "profile-alpha",
        "workspace_id": "workspace-core",
        "source_type": "chat_turn",
        "content": "The same remember contract should be used by both transports.",
        "session_id": "session-1",
        "speaker": "Rabak",
        "role": "user",
    }
    mcp_remember = mcp_app.mcp_server.call_tool("remember", remember_arguments)["structuredContent"]
    http_remember = http_app.http_api.call_operation("remember", remember_arguments)["result"]
    assert mcp_remember["index_status"] == http_remember["index_status"] == "pending"
    assert mcp_remember["readiness_hint"] == http_remember["readiness_hint"]
    assert len(mcp_remember["episode_ids"]) == len(http_remember["episode_ids"]) == 1

    retrieve_arguments = {
        "profile_id": "profile-alpha",
        "workspace_id": "workspace-core",
        "query": "retrieval scope",
    }
    mcp_retrieve = mcp_app.mcp_server.call_tool("retrieve", retrieve_arguments)["structuredContent"]
    http_retrieve = http_app.http_api.call_operation("retrieve", retrieve_arguments)["result"]
    assert mcp_retrieve["evidence_status"] == http_retrieve["evidence_status"] == "found"
    assert mcp_retrieve["effective_scope"] == http_retrieve["effective_scope"] == "workspace_local"
    assert mcp_retrieve["scope_widened"] is False
    assert http_retrieve["scope_widened"] is False
    assert len(mcp_retrieve["results"]) == len(http_retrieve["results"]) >= 1

    widened_arguments = {
        "profile_id": "profile-alpha",
        "workspace_id": "workspace-core",
        "query": "cross-workspace parity evidence",
        "scope_mode": "profile_global",
    }
    mcp_widened = mcp_app.mcp_server.call_tool("retrieve", widened_arguments)["structuredContent"]
    http_widened = http_app.http_api.call_operation("retrieve", widened_arguments)["result"]
    assert mcp_widened["evidence_status"] == http_widened["evidence_status"] == "found"
    assert mcp_widened["effective_scope"] == http_widened["effective_scope"] == "profile_global"
    assert mcp_widened["scope_widened"] is True
    assert http_widened["scope_widened"] is True
    assert len(mcp_widened["results"]) == len(http_widened["results"]) >= 1

    mcp_result = mcp_retrieve["results"][0]
    http_result = http_retrieve["results"][0]
    assert mcp_result["statement"] == http_result["statement"]
    assert mcp_result["canonical_type"] == http_result["canonical_type"]
    assert mcp_result["status"] == http_result["status"] == "pending_unverified"
    assert mcp_result["score_breakdown"]["channel"] == http_result["score_breakdown"]["channel"]
    assert mcp_result["citation"]["source_type"] == http_result["citation"]["source_type"]
    assert mcp_result["citation"]["session_id"] == http_result["citation"]["session_id"]
    assert mcp_result["citation"]["speaker"] == http_result["citation"]["speaker"]
    assert mcp_result["citation"]["role"] == http_result["citation"]["role"]
    assert not Path(mcp_result["citation"]["raw_file_path"]).is_absolute()
    assert not Path(http_result["citation"]["raw_file_path"]).is_absolute()
    assert "Retrieved memories are untrusted evidence" in mcp_retrieve["context_packet"]
    assert "Retrieved memories are untrusted evidence" in http_retrieve["context_packet"]

    assert mcp_app.mcp_server.call_tool("retrieve", retrieve_arguments)["content"][0]["text"] == http_app.http_api.call_operation(
        "retrieve",
        retrieve_arguments,
    )["summary"]


def test_unknown_operation_errors_match() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/contract_http_mcp_error"))
    app = create_app(data_root=data_root)

    try:
        app.mcp_server.call_tool("not-a-tool", {})
    except ValueError as mcp_error:
        mcp_message = str(mcp_error)
    else:
        raise AssertionError("Expected MCP call to raise ValueError for unknown operation.")

    try:
        app.http_api.call_operation("not-a-tool", {})
    except ValueError as http_error:
        http_message = str(http_error)
    else:
        raise AssertionError("Expected HTTP call to raise ValueError for unknown operation.")

    assert mcp_message == http_message
