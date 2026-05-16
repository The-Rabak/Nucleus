from __future__ import annotations

from pathlib import Path

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
