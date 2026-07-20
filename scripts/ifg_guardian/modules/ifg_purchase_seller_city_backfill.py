"""Guardian IFG — backfill seller_snapshot.city dla zakupów (GWO-IFG-0029).

Produkcja: uruchamia ``python -m app.services.purchase_seller_city_backfill``
w kontenerze ``api`` na DS723+ (obraz zawiera pakiet app/).
"""

from __future__ import annotations

import shlex
import subprocess
import sys

from ifg_guardian.config import ROOT
from ifg_guardian.core.deploy_config import load_ds723_config


def run_purchase_seller_city_backfill(*, apply: bool = False, limit: int | None = None) -> int:
    cfg = load_ds723_config()
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"IFG Guardian — purchase seller city backfill ({mode}) on {cfg.host}")
    print("=" * 50)

    py_args = ["python", "-m", "app.services.purchase_seller_city_backfill"]
    if apply:
        py_args.append("--apply")
    if limit is not None:
        py_args.extend(["--limit", str(limit)])

    remote_cmd = (
        f"cd {shlex.quote(cfg.remote_path)} && "
        f"export PATH=\"{cfg.docker_path}:$PATH\" && "
        f"docker compose -f {shlex.quote(cfg.compose_file)} exec -T api "
        + " ".join(shlex.quote(a) for a in py_args)
    )

    ssh_cmd = [
        "ssh",
        "-p",
        str(cfg.port),
        f"{cfg.user}@{cfg.host}",
        remote_cmd,
    ]
    print(f"Ran: {' '.join(ssh_cmd)}")
    completed = subprocess.run(ssh_cmd, cwd=str(ROOT), check=False)
    return int(completed.returncode)
