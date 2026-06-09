from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .business_logic import extract_products
from .excel_reader import WorkbookData, read_workbook


def file_readiness(workbook: WorkbookData) -> Dict[str, Any]:
    products = extract_products(workbook)
    roles = []
    for t in workbook.tables:
        roles.extend(list((t.schema.roles.keys() if t.schema else [])))
    role_set = set(roles)
    readiness = {
        "invoice": bool(products and ("unit_price" in role_set or "unit_cost" in role_set)),
        "quotation": bool(products and ("unit_price" in role_set or "unit_cost" in role_set)),
        "margin_analysis": bool(products and "unit_price" in role_set and any(r in role_set for r in ["unit_cost", "material_cost", "labor_cost", "handling_cost", "overhead_cost"])),
        "production_optimization": bool(products and "location" in role_set and any(r in role_set for r in ["unit_cost", "material_cost", "labor_cost", "handling_cost", "overhead_cost"])),
        "product_comparison": bool(products),
        "scenario_analysis": bool(products and "unit_price" in role_set and any(r in role_set for r in ["unit_cost", "material_cost", "labor_cost", "handling_cost", "overhead_cost"])),
        "question_analysis": bool(workbook.tables and products),
        "goal_analysis": bool(workbook.tables and products),
        "schema_report": bool(workbook.tables),
        "full_report": bool(workbook.tables),
    }
    return readiness


def build_plan(file_paths: Sequence[str], options: Dict[str, Any]) -> Dict[str, Any]:
    outputs = options.get("outputs") or ["full_report"]
    formats = options.get("formats") or ["html"]
    plan: Dict[str, Any] = {
        "ok": True,
        "requires_confirmation": True,
        "message": "This is a proposed plan only. No analysis outputs have been generated yet.",
        "outputs_requested": outputs,
        "formats_requested": formats,
        "files": [],
        "warnings": [],
        "next_step": "Confirm the plan or change options before generation.",
    }
    for path in file_paths:
        wb = read_workbook(path)
        products = extract_products(wb)
        readiness = file_readiness(wb)
        blocked = [o for o in outputs if not readiness.get(o, False)]
        suggested = []
        if blocked:
            suggested.append("Generate schema_report first or adjust column mapping/selected outputs.")
        if any("competitor" in (t.schema.roles if t.schema else {}) for t in wb.tables):
            suggested.append("Competitor/market benchmark data appears present and can be used for product comparison.")
        elif "product_comparison" in outputs:
            suggested.append("No explicit competitor sheet detected. Market comparison will be limited to internal products unless you add market files or agent web research.")
        file_plan = {
            "path": path,
            "filename": wb.filename,
            "errors": wb.errors,
            "table_count": len(wb.tables),
            "detected_product_rows": len(products),
            "sample_products": [
                {"id": p.id, "sku": p.sku, "name": p.name, "location": p.location, "unit_price": p.unit_price, "unit_cost": p.total_cost()}
                for p in products[:8]
            ],
            "sheets": wb.schema_summary(),
            "readiness": readiness,
            "blocked_outputs": blocked,
            "suggestions": suggested,
            "planned_actions": [
                {"output": o, "status": "ready" if readiness.get(o, False) else "needs_review"}
                for o in outputs
            ],
        }
        if blocked:
            plan["warnings"].append(f"{wb.filename}: some requested outputs need review: {', '.join(blocked)}")
        plan["files"].append(file_plan)
    return plan


def plan_to_markdown(plan: Dict[str, Any]) -> str:
    lines = ["# Proposed Business Excel Processing Plan", "", plan.get("message", ""), ""]
    lines.append(f"Outputs: {', '.join(plan.get('outputs_requested', []))}")
    lines.append(f"Formats: {', '.join(plan.get('formats_requested', []))}")
    lines.append("")
    for f in plan.get("files", []):
        lines.append(f"## {f.get('filename')}")
        lines.append(f"- Path: {f.get('path')}")
        lines.append(f"- Sheets detected: {f.get('table_count')}")
        lines.append(f"- Product rows detected: {f.get('detected_product_rows')}")
        if f.get("blocked_outputs"):
            lines.append(f"- Needs review: {', '.join(f['blocked_outputs'])}")
        for action in f.get("planned_actions", []):
            lines.append(f"  - {action['output']}: {action['status']}")
        if f.get("suggestions"):
            lines.append("- Suggestions:")
            for s in f["suggestions"]:
                lines.append(f"  - {s}")
        lines.append("")
    if plan.get("warnings"):
        lines.append("## Warnings")
        for w in plan["warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines)
