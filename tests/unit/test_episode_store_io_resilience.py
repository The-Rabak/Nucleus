from __future__ import annotations

from pathlib import Path

import pytest

from nucleus.adapters.filesystem.episode_store import EpisodeStore
from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_episode_persist_uses_atomic_replace_without_tmp_residue() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_episode_atomic_write"))
    app = create_app(data_root=data_root)

    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Atomic write coverage entry.",
    )

    episode_root = data_root / "profiles" / "profile-alpha" / "workspaces" / "workspace-core" / "episodes"
    markdown_files = list(episode_root.rglob("*.md"))
    assert markdown_files
    assert all(path.read_text(encoding="utf-8").startswith("---\n") for path in markdown_files)

    temp_files = list(episode_root.rglob("*.tmp"))
    assert temp_files == []


def test_lifecycle_corruption_fails_closed_for_retrieve() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_lifecycle_corruption_fail_closed"))
    app = create_app(data_root=data_root)
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Lifecycle corruption should fail closed.",
    )

    lifecycle_state_path = (
        data_root
        / "profiles"
        / "profile-alpha"
        / "workspaces"
        / "workspace-core"
        / "lifecycle"
        / "state.json"
    )
    lifecycle_state_path.parent.mkdir(parents=True, exist_ok=True)
    lifecycle_state_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ValueError, match="Lifecycle state is corrupt"):
        app.retrieve.execute(
            profile_id="profile-alpha",
            workspace_id="workspace-core",
            query="Lifecycle corruption",
        )


def test_lifecycle_audit_events_are_compacted_to_budget() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_lifecycle_audit_budget"))
    store = EpisodeStore(data_root=data_root)
    lifecycle_state = store._default_lifecycle_state()

    for offset in range(256):
        store._append_audit_event(
            lifecycle_state=lifecycle_state,
            operation="forget",
            scope_mode="workspace_local",
            token_id=f"token-{offset}",
            selected_episode_ids=[f"ep-{offset}"],
            recorded_at=f"2026-05-16T00:00:{offset % 60:02d}+00:00",
            replacement_episode_id=None,
        )

    audit_events = lifecycle_state["audit_events"]
    assert len(audit_events) == 200
    oldest = audit_events[0]
    newest = audit_events[-1]
    assert oldest["token_id"] == "token-56"
    assert newest["token_id"] == "token-255"
