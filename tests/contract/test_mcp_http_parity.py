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

    mcp_update_preview = mcp_app.mcp_server.call_tool(
        "update_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Shared adapter parity should preserve retrieval scope",
        },
    )["structuredContent"]
    http_update_preview = http_app.http_api.call_operation(
        "update_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Shared adapter parity should preserve retrieval scope",
        },
    )["result"]
    assert mcp_update_preview["effective_scope"] == http_update_preview["effective_scope"] == "workspace_local"
    assert len(mcp_update_preview["candidates"]) == len(http_update_preview["candidates"]) >= 1
    assert (
        mcp_update_preview["selection"]["requires_explicit_ids"]
        == http_update_preview["selection"]["requires_explicit_ids"]
        is True
    )
    assert (
        mcp_update_preview["selection"]["minimum_selected"]
        == http_update_preview["selection"]["minimum_selected"]
        == 1
    )
    assert (
        len(mcp_update_preview["selection"]["allowed_candidate_ids"])
        == len(http_update_preview["selection"]["allowed_candidate_ids"])
        == len(mcp_update_preview["candidates"])
    )
    assert mcp_update_preview["scope"] == http_update_preview["scope"]

    mcp_update_confirm = mcp_app.mcp_server.call_tool(
        "update_confirm",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "preview_token": mcp_update_preview["preview_token"],
            "selected_episode_ids": [mcp_update_preview["candidates"][0]["episode_id"]],
            "replacement_content": "Updated parity contract memory for update_confirm.",
            "session_id": "session-1",
            "speaker": "Rabak",
            "role": "user",
        },
    )["structuredContent"]
    http_update_confirm = http_app.http_api.call_operation(
        "update_confirm",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "preview_token": http_update_preview["preview_token"],
            "selected_episode_ids": [http_update_preview["candidates"][0]["episode_id"]],
            "replacement_content": "Updated parity contract memory for update_confirm.",
            "session_id": "session-1",
            "speaker": "Rabak",
            "role": "user",
        },
    )["result"]
    assert mcp_update_confirm["applied_count"] == http_update_confirm["applied_count"] == 1
    assert len(mcp_update_confirm["superseded_episode_ids"]) == len(http_update_confirm["superseded_episode_ids"]) == 1
    assert mcp_update_confirm["effective_scope"] == http_update_confirm["effective_scope"] == "workspace_local"
    assert mcp_update_confirm["scope_policy"] == http_update_confirm["scope_policy"]
    assert (
        mcp_update_confirm["audit"]["operation"]
        == http_update_confirm["audit"]["operation"]
        == "update_confirm"
    )

    mcp_forget_preview = mcp_app.mcp_server.call_tool(
        "forget_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Updated parity contract memory for update_confirm.",
        },
    )["structuredContent"]
    http_forget_preview = http_app.http_api.call_operation(
        "forget_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Updated parity contract memory for update_confirm.",
        },
    )["result"]
    assert mcp_forget_preview["effective_scope"] == http_forget_preview["effective_scope"] == "workspace_local"
    assert len(mcp_forget_preview["candidates"]) == len(http_forget_preview["candidates"]) >= 1
    assert (
        mcp_forget_preview["selection"]["requires_explicit_ids"]
        == http_forget_preview["selection"]["requires_explicit_ids"]
        is True
    )
    assert (
        mcp_forget_preview["selection"]["minimum_selected"]
        == http_forget_preview["selection"]["minimum_selected"]
        == 1
    )
    assert (
        len(mcp_forget_preview["selection"]["allowed_candidate_ids"])
        == len(http_forget_preview["selection"]["allowed_candidate_ids"])
        == len(mcp_forget_preview["candidates"])
    )

    mcp_forget_confirm = mcp_app.mcp_server.call_tool(
        "forget_confirm",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "preview_token": mcp_forget_preview["preview_token"],
            "selected_episode_ids": [mcp_forget_preview["candidates"][0]["episode_id"]],
        },
    )["structuredContent"]
    http_forget_confirm = http_app.http_api.call_operation(
        "forget_confirm",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "preview_token": http_forget_preview["preview_token"],
            "selected_episode_ids": [http_forget_preview["candidates"][0]["episode_id"]],
        },
    )["result"]
    assert len(mcp_forget_confirm["forgotten_episode_ids"]) == len(http_forget_confirm["forgotten_episode_ids"]) == 1
    assert mcp_forget_confirm["effective_scope"] == http_forget_confirm["effective_scope"] == "workspace_local"
    assert mcp_forget_confirm["scope_policy"] == http_forget_confirm["scope_policy"]
    assert (
        mcp_forget_confirm["audit"]["operation"]
        == http_forget_confirm["audit"]["operation"]
        == "forget_confirm"
    )

    checkpoint_arguments = {
        "profile_id": "profile-alpha",
        "workspace_id": "workspace-core",
        "session_id": "session-1",
        "trigger": "manual",
        "idempotency_key": "contract-parity-1",
    }
    mcp_checkpoint = mcp_app.mcp_server.call_tool("checkpoint_session", checkpoint_arguments)["structuredContent"]
    http_checkpoint = http_app.http_api.call_operation("checkpoint_session", checkpoint_arguments)["result"]
    assert mcp_checkpoint["effective_scope"] == http_checkpoint["effective_scope"] == "workspace_local"
    assert mcp_checkpoint["trigger"] == http_checkpoint["trigger"] == "manual"
    assert mcp_checkpoint["readiness"] == http_checkpoint["readiness"]
    assert mcp_checkpoint["idempotent"] == http_checkpoint["idempotent"] is False
    assert mcp_checkpoint["observability"]["checkpoint_phase"]["max_audit_events"] == 200
    assert http_checkpoint["observability"]["checkpoint_phase"]["max_audit_events"] == 200

    inspect_arguments = {
        "profile_id": "profile-alpha",
        "workspace_id": "workspace-core",
        "session_id": "session-1",
    }
    mcp_inspect = mcp_app.mcp_server.call_tool("inspect_status", inspect_arguments)["structuredContent"]
    http_inspect = http_app.http_api.call_operation("inspect_status", inspect_arguments)["result"]
    assert mcp_inspect["effective_scope"] == http_inspect["effective_scope"] == "workspace_local"
    assert mcp_inspect["readiness"] == http_inspect["readiness"]
    assert bool(mcp_inspect["latest_checkpoint"]) is True
    assert bool(http_inspect["latest_checkpoint"]) is True
    assert mcp_inspect["latest_checkpoint"]["trigger"] == http_inspect["latest_checkpoint"]["trigger"] == "manual"

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
    assert "inspect_status()" in mcp_bootcard["markdown"]
    assert "checkpoint_session()" in mcp_bootcard["markdown"]
    assert "update_preview()/update_confirm()" in mcp_bootcard["markdown"]
    assert "forget_preview()/forget_confirm()" in mcp_bootcard["markdown"]
    assert "inspect_status()" in http_bootcard["markdown"]
    assert "checkpoint_session()" in http_bootcard["markdown"]
    assert "update_preview()/update_confirm()" in http_bootcard["markdown"]
    assert "forget_preview()/forget_confirm()" in http_bootcard["markdown"]

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
