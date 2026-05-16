from __future__ import annotations

from pathlib import Path

import pytest

from nucleus.infra.app_factory import create_app
from nucleus.testing.sandbox import reset_sandbox


def test_checkpoint_persists_summary_and_bootstrap_continuity() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_continuity"))
    app = create_app(data_root=data_root)

    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Continuity fact: Alpha budget is 1200 USD.",
        session_id="session-42",
        speaker="Rabak",
        role="user",
    )

    checkpoint = app.checkpoint_session.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="pre_compact",
        idempotency_key="precompact-event-1",
    )

    assert checkpoint.trigger == "pre_compact"
    assert checkpoint.effective_scope == "workspace_local"
    assert checkpoint.readiness["truthful"] is True
    assert checkpoint.summary
    assert checkpoint.citations

    status = app.inspect_status.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
    )
    assert status.latest_checkpoint is not None
    assert status.latest_checkpoint["checkpoint_id"] == checkpoint.checkpoint_id

    bootcard = app.bootcard.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
    )
    assert "Latest checkpoint" in bootcard.markdown
    assert checkpoint.checkpoint_id in bootcard.markdown


def test_checkpoint_replay_is_idempotent() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_idempotent"))
    app = create_app(data_root=data_root)

    first = app.checkpoint_session.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="stop",
        idempotency_key="stop-event-1",
    )
    replay = app.checkpoint_session.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="stop",
        idempotency_key="stop-event-1",
    )

    assert replay.checkpoint_id == first.checkpoint_id
    assert replay.recorded_at == first.recorded_at


def test_interrupted_checkpoint_write_recovers_atomically(monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_atomic_recovery"))
    app = create_app(data_root=data_root)

    service = app.checkpoint_session
    original_write = service._atomic_write_json

    interrupted = {"value": False}

    def flaky_write(path: Path, payload: dict[str, object]) -> None:
        if path.name == "latest.json" and not interrupted["value"]:
            interrupted["value"] = True
            temp_path = path.with_name(f".{path.name}.forced.tmp")
            temp_path.write_text("{}", encoding="utf-8")
            raise OSError("simulated interrupted write")
        original_write(path, payload)

    monkeypatch.setattr(service, "_atomic_write_json", flaky_write)

    with pytest.raises(OSError, match="simulated interrupted write"):
        service.execute(
            profile_id="profile-alpha",
            workspace_id="workspace-core",
            session_id="session-42",
            trigger="pre_compact",
            idempotency_key="recoverable-event-1",
        )

    recovered = service.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="pre_compact",
        idempotency_key="recoverable-event-1",
    )

    checkpoint_root = (
        data_root
        / "profiles"
        / "profile-alpha"
        / "workspaces"
        / "workspace-core"
        / "checkpoints"
        / "sessions"
        / "session-42"
    )
    assert (checkpoint_root / f"{recovered.checkpoint_id}.json").exists()
    assert (checkpoint_root / "latest.json").exists()
    assert recovered.idempotent is True
    assert list(checkpoint_root.glob("*.tmp")) == []
    assert list(checkpoint_root.glob(".*.tmp")) == []
