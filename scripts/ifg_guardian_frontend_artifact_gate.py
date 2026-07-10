#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.frontend_artifacts import remote_artifact_verify_script, verify_local_dist
from ifg_guardian.core.deploy_config import DS723Config


def _emit_local_gate() -> int:
    root = Path(__file__).resolve().parents[1]
    gate = verify_local_dist(root)
    print(f"ARTIFACT_GATE_STATUS={gate.status}")
    print(f"ARTIFACT_GATE_MESSAGE={gate.message}")
    print(f"ARTIFACT_INDEX_HTML={'present' if gate.index_html else 'missing'}")
    print(f"ARTIFACT_ASSETS_DIR={'present' if gate.assets_dir else 'missing'}")
    print(f"ARTIFACT_JS_COUNT={gate.js_count}")
    return 0 if gate.is_go else 1


def _emit_remote_gate() -> int:
    cfg = DS723Config.from_context()
    cmd = [
        "ssh",
        "-p",
        str(cfg.port),
        cfg.ssh_target,
        remote_artifact_verify_script(cfg.repo),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"local", "remote"}:
        print("Usage: ifg_guardian_frontend_artifact_gate.py [local|remote]", file=sys.stderr)
        return 2
    if argv[1] == "local":
        return _emit_local_gate()
    return _emit_remote_gate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
