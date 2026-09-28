#!/usr/bin/env python3
"""Stable entrypoint for managed prod-monitor runtime (lives outside immutable releases).

Copied to:
  ~/Library/Application Support/Guardian/ifg-prod-monitor/runner.py

Resolves `current` symlink, sets durable STATE/LOG dirs, then runs monitor check.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RUNTIME_HOME = Path(__file__).resolve().parent
CURRENT = (RUNTIME_HOME / "current").resolve()
SCRIPTS = CURRENT / "scripts"
STATE_DIR = RUNTIME_HOME / "runtime" / "state"
LOG_DIR = RUNTIME_HOME / "runtime" / "logs"


def main() -> int:
    if not SCRIPTS.is_dir():
        print(f"FATAL: current release scripts missing: {SCRIPTS}", file=sys.stderr)
        return 78  # EX_CONFIG
    os.environ["IFG_GUARDIAN_STATE_DIR"] = str(STATE_DIR)
    os.environ["IFG_GUARDIAN_LOG_DIR"] = str(LOG_DIR)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SCRIPTS))
    from ifg_guardian.modules.production_monitor import run_prod_monitor_check

    return int(run_prod_monitor_check())


if __name__ == "__main__":
    raise SystemExit(main())
