from __future__ import annotations

from pathlib import Path

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_scoping_case_14_profile_workspace_boundaries() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/bench_scoping_case_14"))
    app = create_app(data_root=data_root)

    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-a1",
        source_type="chat_turn",
        content="Project Atlas uses Python.",
    )
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-a1",
        source_type="chat_turn",
        content="Atlas deployment target is local Docker.",
    )
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-a2",
        source_type="chat_turn",
        content="Atlas deployment target is Fly.io.",
    )
    app.remember.execute_from_fields(
        profile_id="profile-beta",
        workspace_id="workspace-b1",
        source_type="chat_turn",
        content="Project Atlas uses Rust.",
    )

    profile_a_local = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-a1",
        query="Project Atlas uses",
    )
    assert profile_a_local.effective_scope == "workspace_local"
    assert profile_a_local.scope_widened is False
    assert any("Python" in result["statement"] for result in profile_a_local.results)
    assert all("Rust" not in result["statement"] for result in profile_a_local.results)

    profile_b_local = app.retrieve.execute(
        profile_id="profile-beta",
        workspace_id="workspace-b1",
        query="Project Atlas uses",
    )
    assert profile_b_local.effective_scope == "workspace_local"
    assert profile_b_local.scope_widened is False
    assert any("Rust" in result["statement"] for result in profile_b_local.results)
    assert all("Python" not in result["statement"] for result in profile_b_local.results)

    workspace_a1 = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-a1",
        query="deployment target",
    )
    assert any("local Docker" in result["statement"] for result in workspace_a1.results)
    assert all("Fly.io" not in result["statement"] for result in workspace_a1.results)

    workspace_a2 = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-a2",
        query="deployment target",
    )
    assert any("Fly.io" in result["statement"] for result in workspace_a2.results)
    assert all("local Docker" not in result["statement"] for result in workspace_a2.results)

    widened_profile_a = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-a1",
        query="deployment target",
        top_k=10,
        scope_mode="profile_global",
    )
    assert widened_profile_a.effective_scope == "profile_global"
    assert widened_profile_a.scope_widened is True
    assert any("local Docker" in result["statement"] for result in widened_profile_a.results)
    assert any("Fly.io" in result["statement"] for result in widened_profile_a.results)
    assert all(
        "profile-beta" not in result["citation"]["raw_file_path"]
        for result in widened_profile_a.results
    )

    local_after_widen = app.retrieve.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-a1",
        query="Fly.io",
    )
    assert local_after_widen.effective_scope == "workspace_local"
    assert local_after_widen.scope_widened is False
    assert local_after_widen.evidence_status == "none"
