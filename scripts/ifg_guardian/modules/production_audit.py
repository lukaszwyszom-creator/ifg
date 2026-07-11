"""Read production runtime audit trail."""
from __future__ import annotations

import json

from ifg_guardian.core.runtime_audit import read_audit_records


def run_prod_audit(*, last: int | None = None, since_hours: float | None = None) -> int:
    print("IFG Guardian — prod audit")
    print("=" * 40)
    records = read_audit_records(last=last, since_hours=since_hours)
    if not records:
        print("(no records)")
        return 0
    for item in records:
        print(json.dumps(item, ensure_ascii=False))
    print(f"\nTotal: {len(records)} record(s)")
    return 0
