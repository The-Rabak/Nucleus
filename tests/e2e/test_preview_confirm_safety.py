from __future__ import annotations

from pathlib import Path

import pytest

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def _tamper_preview_token(token: str) -> str:
    prefix, payload, signature = token.split(".")
    replacement = "A" if payload[-1] != "A" else "B"
    tampered_payload = f"{payload[:-1]}{replacement}"
    return f"{prefix}.{tampered_payload}.{signature}"


def test_preview_confirm_safety_lifecycle() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/e2e_preview_confirm_safety"))
    app = create_app(data_root=data_root)

    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Project Atlas budget is 1200 USD.",
        session_id="session-1",
        speaker="Rabak",
        role="user",
    )
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Legacy codename is Sparrow.",
        session_id="session-1",
        speaker="Rabak",
        role="user",
    )

    preview_update_stale = app.mcp_server.call_tool(
        "update_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Atlas budget 1200",
        },
    )["structuredContent"]
    preview_update_fresh = app.mcp_server.call_tool(
        "update_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Atlas budget 1200",
        },
    )["structuredContent"]

    assert preview_update_fresh["selection"]["requires_explicit_ids"] is True
    assert preview_update_fresh["selection"]["minimum_selected"] == 1
    assert preview_update_fresh["ttl_seconds"] > 0
    assert preview_update_fresh["effective_scope"] == "workspace_local"
    assert preview_update_fresh["scope"]["profile_id"] == "profile-alpha"
    assert preview_update_fresh["scope"]["workspace_id"] == "workspace-core"

    update_candidate = preview_update_fresh["candidates"][0]["episode_id"]
    assert update_candidate in preview_update_fresh["candidate_integrity"]
    assert preview_update_fresh["candidate_integrity"][update_candidate]["source_hash"].startswith("sha256:")

    with pytest.raises(ValueError, match="stale"):
        app.mcp_server.call_tool(
            "update_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": preview_update_stale["preview_token"],
                "selected_episode_ids": [update_candidate],
                "replacement_content": "Project Atlas budget is 1300 USD after update.",
            },
        )

    with pytest.raises(ValueError, match="scope"):
        app.mcp_server.call_tool(
            "update_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-other",
                "preview_token": preview_update_fresh["preview_token"],
                "selected_episode_ids": [update_candidate],
                "replacement_content": "Project Atlas budget is 1300 USD after update.",
            },
        )

    with pytest.raises(ValueError, match="signature mismatch"):
        app.mcp_server.call_tool(
            "update_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": _tamper_preview_token(preview_update_fresh["preview_token"]),
                "selected_episode_ids": [update_candidate],
                "replacement_content": "Project Atlas budget is 1300 USD after update.",
            },
        )

    update_confirm = app.mcp_server.call_tool(
        "update_confirm",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "preview_token": preview_update_fresh["preview_token"],
            "selected_episode_ids": [update_candidate],
            "replacement_content": "Project Atlas budget is 1300 USD after update.",
            "source_type": "manual_update",
            "session_id": "session-1",
            "speaker": "Rabak",
            "role": "user",
        },
    )["structuredContent"]

    assert update_confirm["applied_count"] == 1
    assert update_confirm["superseded_episode_ids"] == [update_candidate]
    assert update_confirm["replacement_episode_id"].startswith("ep_")
    assert update_confirm["audit"]["preserved"] is True

    with pytest.raises(ValueError, match="stale"):
        app.mcp_server.call_tool(
            "update_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": preview_update_fresh["preview_token"],
                "selected_episode_ids": [update_candidate],
                "replacement_content": "Project Atlas budget is 1300 USD after update.",
            },
        )

    old_retrieve = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        query="1200",
    )
    assert old_retrieve.evidence_status == "none"

    new_retrieve = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        query="1300 USD",
    )
    assert new_retrieve.evidence_status == "found"

    preview_forget_stale = app.http_api.call_operation(
        "forget_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Legacy codename Sparrow",
        },
    )["result"]
    preview_forget_fresh = app.http_api.call_operation(
        "forget_preview",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "query": "Legacy codename Sparrow",
        },
    )["result"]

    forget_candidate = preview_forget_fresh["candidates"][0]["episode_id"]

    with pytest.raises(ValueError, match="stale"):
        app.http_api.call_operation(
            "forget_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": preview_forget_stale["preview_token"],
                "selected_episode_ids": [forget_candidate],
            },
        )

    with pytest.raises(ValueError, match="mismatch"):
        app.http_api.call_operation(
            "forget_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": preview_forget_fresh["preview_token"],
                "selected_episode_ids": ["ep_unknown"],
            },
        )

    with pytest.raises(ValueError, match="signature mismatch"):
        app.http_api.call_operation(
            "forget_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": _tamper_preview_token(preview_forget_fresh["preview_token"]),
                "selected_episode_ids": [forget_candidate],
            },
        )

    forget_confirm = app.http_api.call_operation(
        "forget_confirm",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "preview_token": preview_forget_fresh["preview_token"],
            "selected_episode_ids": [forget_candidate],
        },
    )["result"]

    assert forget_confirm["forgotten_episode_ids"] == [forget_candidate]
    assert forget_confirm["audit"]["preserved"] is True

    with pytest.raises(ValueError, match="stale"):
        app.http_api.call_operation(
            "forget_confirm",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "preview_token": preview_forget_fresh["preview_token"],
                "selected_episode_ids": [forget_candidate],
            },
        )

    forgotten_retrieve = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        query="Sparrow",
    )
    assert forgotten_retrieve.evidence_status == "none"
