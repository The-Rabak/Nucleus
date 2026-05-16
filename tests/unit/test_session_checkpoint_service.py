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
    checkpoint_phase = checkpoint.observability["checkpoint_phase"]
    assert checkpoint_phase["citation_count"] == len(checkpoint.citations)
    assert checkpoint_phase["preview_token_count"] == len(checkpoint.preview_tokens)
    assert checkpoint_phase["audit_event_count"] >= 0
    assert checkpoint_phase["max_audit_events"] == 200

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


def test_checkpoint_includes_preview_token_snapshot_by_default() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_preview_tokens_default"))
    app = create_app(data_root=data_root)
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Preview snapshot anchor for checkpoint.",
        session_id="session-42",
        speaker="Rabak",
        role="user",
    )
    preview = app.update_preview.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        query="Preview snapshot anchor",
    )
    checkpoint = app.checkpoint_session.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="manual",
        idempotency_key="manual-event-preview-default",
    )

    assert checkpoint.preview_tokens
    assert checkpoint.warnings == []
    snapshot_entry = checkpoint.preview_tokens["update:workspace_local"]
    assert snapshot_entry["token_id"] == preview.token_id
    assert "claims_digest" in snapshot_entry


def test_checkpoint_can_exclude_preview_token_snapshot() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_preview_tokens_excluded"))
    app = create_app(data_root=data_root)
    app.remember.execute_from_fields(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        source_type="chat_turn",
        content="Exclude preview snapshot anchor for checkpoint.",
        session_id="session-42",
        speaker="Rabak",
        role="user",
    )
    app.update_preview.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        query="Exclude preview snapshot anchor",
    )
    checkpoint = app.checkpoint_session.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="manual",
        idempotency_key="manual-event-preview-excluded",
        include_preview_tokens=False,
    )
    status = app.inspect_status.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
    )

    assert checkpoint.preview_tokens == {}
    assert checkpoint.warnings == ["preview token snapshot was excluded"]
    assert status.latest_checkpoint is not None
    assert status.latest_checkpoint["preview_tokens"] == {}


def test_inspect_status_reports_checkpoint_corruption_warning() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_corruption_warning"))
    app = create_app(data_root=data_root)
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
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    (checkpoint_root / "latest.json").write_text("{invalid json", encoding="utf-8")

    status = app.inspect_status.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
    )

    assert status.latest_checkpoint is None
    assert status.warnings
    assert "checkpoint_state_corrupt" in status.warnings[0]


def test_latest_checkpoint_uses_pointer_when_latest_json_missing() -> None:
    data_root = reset_sandbox(Path("tests/.sandbox/unit_checkpoint_latest_pointer"))
    app = create_app(data_root=data_root)
    checkpoint = app.checkpoint_session.execute(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
        trigger="manual",
        idempotency_key="manual-event-latest-pointer",
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
    latest_path = checkpoint_root / "latest.json"
    latest_path.unlink()

    latest = app.checkpoint_session.latest_checkpoint(
        profile_id="profile-alpha",
        workspace_id="workspace-core",
        session_id="session-42",
    )

    assert latest is not None
    assert latest["checkpoint_id"] == checkpoint.checkpoint_id
    assert (checkpoint_root / "latest.pointer").exists()
    assert latest_path.exists()
