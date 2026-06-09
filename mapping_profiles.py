from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .excel_reader import WorkbookData
from .schema_mapper import ColumnMatch


def load_mapping_profile(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Mapping profile not found: {p}")
    if p.suffix.lower() in {".json", ".map"}:
        return json.loads(p.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"Mapping profile must be JSON or YAML. Could not read {p}: {exc}")


def apply_mapping_profile(workbook: WorkbookData, mapping: Dict[str, Any]) -> WorkbookData:
    if not mapping:
        return workbook
    global_cols = mapping.get("columns", {}) or {}
    sheets = mapping.get("sheets", {}) or {}
    for table in workbook.tables:
        if not table.schema:
            continue
        sheet_mapping = dict(global_cols)
        sheet_mapping.update(sheets.get(table.name, {}) or {})
        sheet_mapping.update(sheets.get("*", {}) or {})
        for role, column in sheet_mapping.items():
            if column in table.dataframe.columns:
                table.schema.roles[str(role)] = ColumnMatch(str(role), str(column), 1.0, "manual mapping profile")
    return workbook


def example_mapping() -> Dict[str, Any]:
    return {
        "name": "example_mapping",
        "description": "Map arbitrary workbook columns to business roles.",
        "columns": {
            "sku": "Item Code",
            "product": "Description",
            "unit_price": "Sales Price EUR",
            "material_cost": "Material Cost",
            "labor_cost": "Direct Labour",
            "handling_cost": "Handling / Logistics",
            "overhead_cost": "Overhead",
            "quantity": "Annual Demand",
            "location": "Plant",
        },
        "sheets": {
            "Production locations": {
                "sku": "Product Code",
                "product": "Product",
                "location": "Country",
                "unit_cost": "Total Unit Cost",
                "capacity": "Capacity",
            }
        },
    }


def write_example_mapping(path: str) -> str:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(example_mapping(), indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p)
