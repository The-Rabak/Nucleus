from __future__ import annotations

from pathlib import Path

import pytest

from nucleus.infra.app_factory import create_app
from nucleus.infra.runtime_config import load_runtime_config


def test_load_runtime_config_reads_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NUCLEUS_DATA_DIR=.nucleus-from-env\n"
        "NUCLEUS_PROFILE_ID=profile-alpha\n"
        "NUCLEUS_WORKSPACE_ID=workspace-core\n"
        "NUCLEUS_REQUIRE_BOUND_SCOPE=true\n",
        encoding="utf-8",
    )
    environ: dict[str, str] = {"NUCLEUS_ENV_FILE": str(env_file)}

    config = load_runtime_config(environ=environ)

    assert config.env_file == env_file
    assert config.data_dir == Path(".nucleus-from-env")
    assert config.bound_profile_id == "profile-alpha"
    assert config.bound_workspace_id == "workspace-core"
    assert config.require_bound_scope is True


def test_create_app_uses_injected_runtime_config(tmp_path: Path) -> None:
    runtime_data_dir = tmp_path / "runtime-data"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NUCLEUS_PROFILE_ID=profile-alpha\nNUCLEUS_WORKSPACE_ID=workspace-core\n",
        encoding="utf-8",
    )
    environ: dict[str, str] = {
        "NUCLEUS_ENV_FILE": str(env_file),
        "NUCLEUS_DATA_DIR": str(runtime_data_dir),
        "NUCLEUS_REQUIRE_BOUND_SCOPE": "true",
    }

    runtime_config = load_runtime_config(environ=environ)
    app = create_app(runtime_config=runtime_config)

    remember_payload = app.mcp_server.call_tool(
        "remember",
        {
            "profile_id": "profile-alpha",
            "workspace_id": "workspace-core",
            "source_type": "chat_turn",
            "content": "runtime config smoke test",
        },
    )
    assert remember_payload["structuredContent"]["index_status"] == "pending"
    assert list(runtime_data_dir.rglob("*.md"))

    with pytest.raises(ValueError, match="profile_id is outside the configured server scope"):
        app.mcp_server.call_tool(
            "remember",
            {
                "profile_id": "profile-beta",
                "workspace_id": "workspace-core",
                "source_type": "chat_turn",
                "content": "out of scope",
            },
        )


def test_load_runtime_config_defaults_scope_binding_mode_to_compatibility() -> None:
    config = load_runtime_config(environ={})
    assert config.require_bound_scope is False
