from __future__ import annotations

from pathlib import Path
import shutil


def reset_sandbox(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
