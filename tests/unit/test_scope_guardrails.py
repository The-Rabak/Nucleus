from __future__ import annotations

from pathlib import Path

import pytest

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_remember_rejects_path_traversal_identifiers() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_scope_guardrails_traversal"))
    app = create_app(data_root=data_root)

    with pytest.raises(ValueError, match="profile_id must match pattern"):
        app.remember.execute_from_fields(
            profile_id="../escape",
            workspace_id="workspace-core",
            source_type="chat_turn",
            content="unsafe",
        )

    with pytest.raises(ValueError, match="workspace_id must match pattern"):
        app.remember.execute_from_fields(
            profile_id="profile-alpha",
            workspace_id="../../escape",
            source_type="chat_turn",
            content="unsafe",
        )


def test_server_scope_binding_rejects_cross_scope_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_scope_guardrails_binding"))
    monkeypatch.setenv("NUCLEUS_PROFILE_ID", "profile-alpha")
    monkeypatch.setenv("NUCLEUS_WORKSPACE_ID", "workspace-core")
    app = create_app(data_root=data_root)

    with pytest.raises(ValueError, match="profile_id is outside the configured server scope"):
        app.mcp_server.call_tool(
            "remember",
            {
                "profile_id": "profile-beta",
                "workspace_id": "workspace-core",
                "source_type": "chat_turn",
                "content": "cross-scope write",
            },
        )

    with pytest.raises(ValueError, match="profile_global scope_mode is outside the configured server scope"):
        app.mcp_server.call_tool(
            "retrieve",
            {
                "profile_id": "profile-alpha",
                "workspace_id": "workspace-core",
                "query": "cross-workspace read",
                "scope_mode": "profile_global",
            },
        )
