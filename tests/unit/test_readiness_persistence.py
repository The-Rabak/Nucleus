from __future__ import annotations

from pathlib import Path

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_pending_readiness_survives_app_restart() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_readiness_persistence"))
    app = create_app(data_root=data_root)
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Persistence check",
    )

    restarted_app = create_app(data_root=data_root)
    bootcard = restarted_app.bootcard.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-1",
    )

    assert bootcard.readiness["index_status"] == "pending"
    assert bootcard.readiness["ready"] is False
    assert bootcard.readiness["truthful"] is True
