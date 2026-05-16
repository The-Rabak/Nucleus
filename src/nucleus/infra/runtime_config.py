from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import MutableMapping


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    data_dir: Path
    env_file: Path
    bound_profile_id: str | None
    bound_workspace_id: str | None
    require_bound_scope: bool


def load_runtime_config(
    *,
    environ: MutableMapping[str, str] | None = None,
    data_root: Path | None = None,
) -> RuntimeConfig:
    target_environ = environ if environ is not None else os.environ
    env_file = Path(target_environ.get("NUCLEUS_ENV_FILE", ".env"))
    load_env_file(env_file=env_file, environ=target_environ)

    return RuntimeConfig(
        data_dir=data_root or Path(target_environ.get("NUCLEUS_DATA_DIR", ".nucleus")),
        env_file=env_file,
        bound_profile_id=target_environ.get("NUCLEUS_PROFILE_ID"),
        bound_workspace_id=target_environ.get("NUCLEUS_WORKSPACE_ID"),
        require_bound_scope=_parse_bool_env(
            target_environ.get("NUCLEUS_REQUIRE_BOUND_SCOPE"),
        ),
    )


def load_env_file(
    *,
    env_file: Path,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    if not env_file.exists():
        return

    target_environ = environ if environ is not None else os.environ
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_value = value.strip().strip("'").strip('"')
        target_environ.setdefault(key.strip(), normalized_value)


def _parse_bool_env(raw_value: str | None) -> bool:
    if raw_value is None:
        return False
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
