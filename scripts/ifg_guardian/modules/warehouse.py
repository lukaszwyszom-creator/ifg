from __future__ import annotations

from ifg_guardian.config import ROOT


def run_warehouse_check() -> int:
    print("IFG Guardian — warehouse check")
    print("=" * 40)

    has_error = False
    checks = [
        ("app/services/warehouse_document_service.py", "Warehouse document service"),
        ("app/services/warehouse_item_service.py", "Warehouse item service"),
        ("app/api/routers/warehouse_documents.py", "Warehouse documents router"),
        ("app/api/routers/warehouse_items.py", "Warehouse items router"),
        ("frontend-react/src/pages/warehouse/WarehousePage.jsx", "Warehouse UI page"),
    ]

    for rel, label in checks:
        path = ROOT / rel
        if path.is_file():
            print(f"✅ {label}: {rel}")
        else:
            has_error = True
            print(f"❌ {label}: brak {rel}")

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    print("Status: OK")
    return 0
