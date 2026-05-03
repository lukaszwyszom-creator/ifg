"""Walidacja przykładowych danych faktur pod testy rozrachunków."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DemoDataValidationReport:
    valid: bool
    errors: list[str]
    checked_invoices: int


def _ast_to_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return f"<{node.id}>"
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_ast_to_value(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        result: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                result[key_node.value] = _ast_to_value(value_node)
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return f"{node.func.id}(...)"
    return "<expr>"


def _parse_seed_monthly_invoices(file_path: Path) -> list[dict[str, Any]]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    target_lists = {"SALE_MARCH", "SALE_APRIL", "PURCHASE_MARCH", "PURCHASE_APRIL"}
    invoices: list[dict[str, Any]] = []
    constants: dict[str, Any] = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        constants[target.id] = _ast_to_value(node.value)

    def _value(node: ast.AST) -> Any:
        if isinstance(node, ast.Name) and node.id in constants:
            return constants[node.id]
        return _ast_to_value(node)

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in target_lists:
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue

        for index, entry in enumerate(node.value.elts, start=1):
            if not isinstance(entry, ast.Dict):
                continue
            invoice: dict[str, Any] = {"_id": f"{target.id}[{index}]", "_source": str(file_path)}
            for key_node, value_node in zip(entry.keys, entry.values):
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    invoice[key_node.value] = _value(value_node)
            invoices.append(invoice)

    return invoices


def _parse_seed_demo_april(file_path: Path) -> list[dict[str, Any]]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    field_order = [
        "seed_key",
        "slug",
        "contractor_slug",
        "direction",
        "issue_date",
        "net_amount",
        "vat_rate",
        "due_date",
    ]
    invoices: list[dict[str, Any]] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "INVOICES":
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue

        for index, entry in enumerate(node.value.elts, start=1):
            if not isinstance(entry, ast.Call):
                continue
            if not isinstance(entry.func, ast.Name) or entry.func.id != "InvoiceSpec":
                continue

            invoice: dict[str, Any] = {"_id": f"INVOICES[{index}]", "_source": str(file_path)}

            for position, arg in enumerate(entry.args):
                if position < len(field_order):
                    invoice[field_order[position]] = _ast_to_value(arg)

            for keyword in entry.keywords:
                if keyword.arg is not None:
                    invoice[keyword.arg] = _ast_to_value(keyword.value)

            invoices.append(invoice)

    return invoices


def _parse_seed_demo_april_contractors(file_path: Path) -> dict[str, str]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    lookup: dict[str, str] = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "CONTRACTORS":
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue

        for entry in node.value.elts:
            if not isinstance(entry, ast.Call):
                continue
            if not isinstance(entry.func, ast.Name) or entry.func.id != "ContractorSpec":
                continue

            slug = _ast_to_value(entry.args[0]) if len(entry.args) > 0 else None
            nip = _ast_to_value(entry.args[1]) if len(entry.args) > 1 else None
            name = _ast_to_value(entry.args[2]) if len(entry.args) > 2 else None

            if isinstance(name, str) and name.strip():
                if isinstance(slug, str) and slug.strip():
                    lookup[slug.strip().lower()] = name.strip()
                if isinstance(nip, str) and nip.strip():
                    lookup[nip.strip().lower()] = name.strip()

    return lookup


def _parse_baseline_contractor_names(file_path: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    contractors = payload.get("contractors")
    if not isinstance(contractors, dict):
        return lookup

    for contractor in contractors.values():
        if not isinstance(contractor, dict):
            continue
        name = contractor.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        for key in ("id", "nip"):
            value = contractor.get(key)
            if isinstance(value, str) and value.strip():
                lookup[value.strip().lower()] = name.strip()

    return lookup


def _merge_contractor_lookups(
    contractors_lookup: dict[str, str],
    baseline_lookup: dict[str, str],
) -> dict[str, str]:
    merged = dict(contractors_lookup)
    for key, value in baseline_lookup.items():
        merged.setdefault(key, value)
    return merged


def _invoice_label(invoice: dict[str, Any], index: int) -> str:
    for key in ("seed_key", "slug", "number_local", "id", "_id"):
        value = invoice.get(key)
        if value not in (None, ""):
            return str(value)
    return f"#{index}"


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _first_non_empty(invoice: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = invoice.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_name_from_lookup(invoice: dict[str, Any], lookup: dict[str, str]) -> str | None:
    for key in ("buyer_id", "seller_id", "contractor_id", "contractor_slug", "nip"):
        value = invoice.get(key)
        if isinstance(value, str) and value.strip():
            candidate = lookup.get(value.strip().lower())
            if candidate:
                return candidate
    return None


def _has_gross_amount(invoice: dict[str, Any]) -> bool:
    for key in ("gross_amount", "total_gross", "amount_gross", "gross"):
        if not _is_missing(invoice.get(key)):
            return True

    totals_json = invoice.get("totals_json")
    if isinstance(totals_json, dict) and not _is_missing(totals_json.get("total_gross")):
        return True

    net_amount = invoice.get("net_amount")
    if not _is_missing(net_amount):
        return True

    items = invoice.get("items")
    if isinstance(items, list) and len(items) > 0:
        return True

    return False


def _has_contractor(invoice: dict[str, Any]) -> bool:
    for key in (
        "buyer_id",
        "seller_id",
        "contractor_id",
        "contractor_slug",
        "buyer_snapshot",
        "seller_snapshot",
        "buyer_snapshot_json",
        "seller_snapshot_json",
    ):
        if not _is_missing(invoice.get(key)):
            return True
    return False


def validate_demo_invoices(
    invoices: list[dict[str, Any]],
    contractor_name_lookup: dict[str, str] | None = None,
) -> DemoDataValidationReport:
    errors: list[str] = []
    contractor_name_lookup = contractor_name_lookup or {}

    for index, invoice in enumerate(invoices, start=1):
        label = _invoice_label(invoice, index)

        if _is_missing(invoice.get("issue_date")):
            errors.append(f"invoice {label}: missing issue_date")

        if _is_missing(invoice.get("due_date")):
            errors.append(f"invoice {label}: missing due_date")

        if not _has_gross_amount(invoice):
            errors.append(f"invoice {label}: missing gross amount")

        if not _has_contractor(invoice):
            errors.append(f"invoice {label}: missing contractor")

        direction = invoice.get("direction")
        if _is_missing(direction):
            errors.append(f"invoice {label}: missing invoice direction (sale/purchase)")
        elif direction not in {"sale", "purchase"}:
            errors.append(f"invoice {label}: invalid invoice direction '{direction}'")
        elif direction == "sale":
            buyer_name = _first_non_empty(invoice, ("buyer_name", "customer_name"))
            if buyer_name is None:
                buyer_name = _resolve_name_from_lookup(invoice, contractor_name_lookup)
            if buyer_name is None:
                errors.append(
                    f"invoice {label}: missing buyer_name for sale invoice (missing_buyer_name)"
                )
        elif direction == "purchase":
            seller_name = _first_non_empty(invoice, ("seller_name", "supplier_name", "vendor_name"))
            if seller_name is None:
                seller_name = _resolve_name_from_lookup(invoice, contractor_name_lookup)
            if seller_name is None:
                errors.append(
                    f"invoice {label}: missing seller_name for purchase invoice (missing_seller_name)"
                )

    return DemoDataValidationReport(
        valid=not errors,
        errors=errors,
        checked_invoices=len(invoices),
    )


def validate_repo_demo_data(root_dir: str = ".") -> DemoDataValidationReport:
    root = Path(root_dir)
    invoices: list[dict[str, Any]] = []
    errors: list[str] = []

    monthly_seed = root / "scripts" / "seed_monthly_invoices.py"
    april_seed = root / "scripts" / "seed_demo_april_2026.py"
    baseline_seed = root / "tests" / "fixtures" / "baseline_seed.json"
    contractors_lookup: dict[str, str] = {}
    baseline_lookup: dict[str, str] = {}

    if monthly_seed.is_file():
        try:
            invoices.extend(_parse_seed_monthly_invoices(monthly_seed))
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(f"seed parse error {monthly_seed}: {exc}")

    if april_seed.is_file():
        try:
            invoices.extend(_parse_seed_demo_april(april_seed))
            contractors_lookup = _parse_seed_demo_april_contractors(april_seed)
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(f"seed parse error {april_seed}: {exc}")

    if baseline_seed.is_file():
        try:
            baseline_lookup = _parse_baseline_contractor_names(baseline_seed)
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(f"seed parse error {baseline_seed}: {exc}")

    if not invoices and not errors:
        errors.append("no demo invoice seeds found in scripts/")

    contractor_lookup = _merge_contractor_lookups(contractors_lookup, baseline_lookup)
    report = validate_demo_invoices(invoices, contractor_name_lookup=contractor_lookup)
    if errors:
        return DemoDataValidationReport(
            valid=False,
            errors=errors + report.errors,
            checked_invoices=report.checked_invoices,
        )
    return report
