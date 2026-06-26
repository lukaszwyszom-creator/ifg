from __future__ import annotations

from ifg_guardian.modules.api_mobile import run_api_guardian
from ifg_guardian.modules.deploy import run_deploy_check
from ifg_guardian.modules.frontend import run_frontend_check
from ifg_guardian.modules.ksef import run_ksef_check
from ifg_guardian.modules.repo import run_repo_audit
from ifg_guardian.modules.warehouse import run_warehouse_check


def run_doctor(*, do_fetch: bool = False) -> int:
    """Aggregate read-only checks — stops at first hard failure for exit code."""
    print("IFG Guardian — doctor")
    print("=" * 40)

    checks: list[tuple[str, int]] = [
        ("repo audit", run_repo_audit(do_fetch=do_fetch)),
        ("frontend check", run_frontend_check()),
        ("ksef check", run_ksef_check()),
        ("warehouse check", run_warehouse_check()),
        ("deploy check", run_deploy_check()),
        ("api mobile", run_api_guardian()),
    ]

    failed = [name for name, code in checks if code != 0]
    print("\n" + "=" * 40)
    print("Doctor summary:")
    for name, code in checks:
        print(f"  {'✅' if code == 0 else '❌'} {name}")

    if failed:
        print(f"\nStatus: ERROR ({len(failed)} check(s) failed)")
        return 1
    print("\nStatus: OK")
    return 0
