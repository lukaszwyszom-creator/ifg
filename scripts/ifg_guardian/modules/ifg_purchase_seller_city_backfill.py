"""Guardian IFG — backfill seller_snapshot.city dla zakupów (GWO-IFG-0029)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ifg_guardian.config import ROOT


def run_purchase_seller_city_backfill(*, apply: bool = False, limit: int | None = None) -> int:
    script = ROOT / "scripts" / "backfill_purchase_seller_city.py"
    if not script.is_file():
        print(f"❌ brak skryptu: {script}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(script)]
    if apply:
        cmd.append("--apply")
    if limit is not None:
        cmd.extend(["--limit", str(limit)])

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"IFG Guardian — purchase seller city backfill ({mode})")
    print("=" * 50)
    print(f"Ran: {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return int(completed.returncode)
