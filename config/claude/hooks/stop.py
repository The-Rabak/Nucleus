#!/usr/bin/env python3
from __future__ import annotations

from checkpoint_hook import run_checkpoint_hook


def main() -> None:
    run_checkpoint_hook(trigger="stop")


if __name__ == "__main__":
    main()
