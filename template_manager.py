from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape

from .business_logic import ProductItem, SelectedLine, extract_products
from .excel_reader import WorkbookData
from .html_renderer import DEFAULT_STYLE, fmt_currency, fmt_number, fmt_pct
from .schema_mapper import safe_number


DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
DEFAULT_USER_TEMPLATE_DIR = Path.home() / ".business_ai_skill" / "templates"


@dataclass
class TemplateInfo:
    name: str
    kind: str
    path: str
    source: str
    description: str = ""


def _template_dir(user_template_dir: Optional[str] = None) -> Path:
    return Path(user_template_dir).expanduser().resolve() if user_template_dir else DEFAULT_USER_TEMPLATE_DIR


def ensure_user_template_dir(user_template_dir: Optional[str] = None) -> Path:
    d = _template_dir(user_template_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kind_from_name(path: Path) -> str:
    n = path.name.lower()
    if "quote" in n or "quotation" in n:
        return "quotation"
    if "invoice" in n:
        return "invoice"
    if "report" in n:
        return "report"
    return "document"


def list_templates(user_template_dir: Optional[str] = None) -> List[TemplateInfo]:
    templates: List[TemplateInfo] = []
    for source, base in [("built-in", DEFAULT_TEMPLATE_DIR), ("user", _template_dir(user_template_dir))]:
        if not base.exists():
            continue
        for path in sorted(base.glob("*.html.j2")):
            name = path.name[: -len(".html.j2")]
            desc = ""
            try:
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:8]:
                    line = line.strip()
                    if line.startswith("{#") and line.endswith("#}"):
                        desc = line.strip("{#} ")
                        break
            except Exception:
                pass
            templates.append(TemplateInfo(name=name, kind=_kind_from_name(path), path=str(path), source=source, description=desc))
    # User templates override same name.
    by_name: Dict[str, TemplateInfo] = {}
    for t in templates:
        if t.name not in by_name or t.source == "user":
            by_name[t.name] = t
    return sorted(by_name.values(), key=lambda t: (t.kind, t.name))


def find_template(name: str, user_template_dir: Optional[str] = None) -> Path:
    name = name.replace(".html.j2", "")
    candidates = [
        _template_dir(user_template_dir) / f"{name}.html.j2",
        DEFAULT_TEMPLATE_DIR / f"{name}.html.j2",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Template '{name}' not found. Available: {[t.name for t in list_templates(user_template_dir)]}")


def create_template(name: str, from_template: str = "invoice_basic", kind: Optional[str] = None, user_template_dir: Optional[str] = None, overwrite: bool = False) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip()).strip("_")
    if not safe_name:
        raise ValueError("Template name cannot be empty")
    if not safe_name.endswith(".html.j2"):
        filename = f"{safe_name}.html.j2"
    else:
        filename = safe_name
    dest_dir = ensure_user_template_dir(user_template_dir)
    dest = dest_dir / filename
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Template already exists: {dest}. Use overwrite=True or --overwrite.")
    src = find_template(from_template, user_template_dir)
    shutil.copy2(src, dest)
    return dest


def update_template(name: str, source_file: str, user_template_dir: Optional[str] = None, overwrite: bool = True) -> Path:
    src = Path(source_file).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source template file not found: {src}")
    if not src.read_text(encoding="utf-8", errors="ignore").strip():
        raise ValueError("Template file is empty")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip()).strip("_")
    if not safe_name.endswith(".html.j2"):
        safe_name = f"{safe_name}.html.j2"
    dest_dir = ensure_user_template_dir(user_template_dir)
    dest = dest_dir / safe_name
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Template already exists: {dest}")
    shutil.copy2(src, dest)
    return dest


def delete_user_template(name: str, user_template_dir: Optional[str] = None) -> Path:
    name = name.replace(".html.j2", "")
    path = _template_dir(user_template_dir) / f"{name}.html.j2"
    if not path.exists():
        raise FileNotFoundError(f"User template not found: {path}")
    path.unlink()
    return path


def read_template(name: str, user_template_dir: Optional[str] = None) -> str:
    return find_template(name, user_template_dir).read_text(encoding="utf-8")


def _env_for_template(template_path: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader([str(template_path.parent), str(DEFAULT_TEMPLATE_DIR)]),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["currency"] = fmt_currency
    env.filters["number"] = fmt_number
    env.filters["pct"] = fmt_pct
    return env


def selected_lines_from_products(
    products: Sequence[ProductItem],
    select: str = "all",
    quantities: Optional[Dict[str, Any]] = None,
    default_qty: float = 1.0,
    max_lines: int = 200,
) -> List[SelectedLine]:
    quantities = quantities or {}
    by_id = {p.id: p for p in products}
    by_sku = {p.sku: p for p in products if p.sku}
    by_name = {p.name: p for p in products if p.name}
    chosen: List[ProductItem] = []
    s = (select or "all").strip()
    if s == "all":
        chosen = list(products[:max_lines])
    elif s == "top-margin":
        chosen = sorted(products, key=lambda p: (p.margin_rate() if p.margin_rate() == p.margin_rate() else -999), reverse=True)[:max_lines]
    elif s == "positive-margin":
        chosen = [p for p in products if p.margin_rate() == p.margin_rate() and p.margin_rate() > 0][:max_lines]
    elif s.startswith("ids:"):
        for pid in [x.strip() for x in s[4:].split(",") if x.strip()]:
            if pid in by_id:
                chosen.append(by_id[pid])
    elif s.startswith("sku:") or s.startswith("skus:"):
        _, values = s.split(":", 1)
        for sku in [x.strip() for x in values.split(",") if x.strip()]:
            if sku in by_sku:
                chosen.append(by_sku[sku])
    else:
        # Interpret comma-separated IDs/SKUs/names.
        for token in [x.strip() for x in s.split(",") if x.strip()]:
            if token in by_id:
                chosen.append(by_id[token])
            elif token in by_sku:
                chosen.append(by_sku[token])
            elif token in by_name:
                chosen.append(by_name[token])
    lines: List[SelectedLine] = []
    for p in chosen:
        qty = default_qty
        for key in [p.id, p.sku, p.name]:
            if key and key in quantities:
                qty = safe_number(quantities[key], default_qty)
                break
        if qty <= 0:
            continue
        lines.append(SelectedLine(product=p, quantity=qty))
    return lines


def make_document_context(
    workbook: WorkbookData,
    document_type: str,
    lines: Sequence[SelectedLine],
    company: str = "Your Company",
    customer: str = "Customer",
    currency: str = "€",
    tax_rate: float = 21.0,
    notes: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    subtotal = sum(line.line_total for line in lines)
    tax = subtotal * (tax_rate / 100.0)
    total = subtotal + tax
    doc_type = "Quotation" if document_type.lower().startswith("quote") else "Invoice"
    prefix = "QUO" if doc_type == "Quotation" else "INV"
    doc_no = f"{prefix}-{date.today().strftime('%Y%m%d')}"
    line_context = []
    for idx, line in enumerate(lines, 1):
        p = line.product
        cost = p.total_cost()
        margin_unit = line.unit_price - cost if cost == cost else math.nan
        line_context.append({
            "index": idx,
            "sku": p.sku,
            "name": p.name or p.display_name(),
            "description": p.name or p.display_name(),
            "category": p.category,
            "location": p.location,
            "supplier": p.supplier,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "discount_pct": line.discount_pct,
            "line_total": line.line_total,
            "unit_cost": cost,
            "margin_unit": margin_unit,
            "margin_pct": margin_unit / line.unit_price if line.unit_price else math.nan,
        })
    context = {
        "style": DEFAULT_STYLE,
        "generated_date": date.today().isoformat(),
        "workbook": {"filename": workbook.filename, "path": workbook.path},
        "document": {
            "type": doc_type,
            "number": doc_no,
            "date": date.today().isoformat(),
            "valid_until": (date.today() + timedelta(days=30)).isoformat(),
            "currency": currency,
            "tax_rate": tax_rate,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "notes": notes,
        },
        "company": {"name": company},
        "customer": {"name": customer},
        "lines": line_context,
        "totals": {"subtotal": subtotal, "tax": tax, "total": total},
        "metadata": extra or {},
    }
    return context


def render_template(template_name: str, context: Dict[str, Any], output_path: str, user_template_dir: Optional[str] = None) -> str:
    template_path = find_template(template_name, user_template_dir)
    env = _env_for_template(template_path)
    template = env.get_template(template_path.name)
    html = template.render(**context)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)


def render_document_template(
    workbook: WorkbookData,
    document_type: str,
    lines: Sequence[SelectedLine],
    output_path: str,
    template_name: Optional[str] = None,
    company: str = "Your Company",
    customer: str = "Customer",
    currency: str = "€",
    tax_rate: float = 21.0,
    notes: str = "",
    user_template_dir: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    if template_name is None:
        template_name = "quotation_basic" if document_type.lower().startswith("quote") else "invoice_basic"
    context = make_document_context(workbook, document_type, lines, company, customer, currency, tax_rate, notes, extra)
    return render_template(template_name, context, output_path, user_template_dir)


def context_json_preview(context: Dict[str, Any]) -> str:
    return json.dumps(context, indent=2, ensure_ascii=False, default=str)
