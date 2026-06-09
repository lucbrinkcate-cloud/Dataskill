from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.business_logic import (
    extract_products,
    full_report,
    goal_analysis,
    margin_analysis,
    product_comparison,
    production_optimization,
    question_analysis,
    scenario_analysis,
    schema_report,
)
from core.excel_reader import read_workbook
from core.llm import OllamaClient
from core.mapping_profiles import apply_mapping_profile, load_mapping_profile, write_example_mapping
from core.template_manager import (
    context_json_preview,
    create_template,
    delete_user_template,
    list_templates,
    make_document_context,
    read_template,
    render_document_template,
    selected_lines_from_products,
    update_template,
)
from core.schema_mapper import safe_number
from core.exporters import export_html
from core.audit import create_audit_record, load_approval_register, set_output_status
from core.session_outputs import session_output_dir
from core.insight_engine import load_review_queue, set_insight_status, load_goal_state

SUPPORTED_OUTPUTS = {
    "invoice",
    "quotation",
    "quote",
    "full_report",
    "margin_analysis",
    "production_optimization",
    "product_comparison",
    "schema_report",
    "scenario_analysis",
    "question_analysis",
    "goal_analysis",
}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def expand_files(patterns: Sequence[str]) -> List[Path]:
    out: List[Path] = []
    for pattern in patterns:
        p = Path(pattern).expanduser()
        if any(ch in str(p) for ch in "*?["):
            matches = sorted(Path().glob(str(p))) if not p.is_absolute() else sorted(Path(p.anchor).glob(str(p)[len(p.anchor):]))
            out.extend([m.resolve() for m in matches if m.is_file()])
        elif p.is_dir():
            for ext in ("*.xlsx", "*.xlsm", "*.xls", "*.csv"):
                out.extend(sorted(p.glob(ext)))
        elif p.exists():
            out.append(p.resolve())
        else:
            eprint(f"Warning: file/pattern not found: {pattern}")
    # Deduplicate preserving order.
    seen = set()
    deduped = []
    for p in out:
        if str(p) not in seen:
            seen.add(str(p))
            deduped.append(p)
    return deduped


def parse_outputs(output: Optional[str] = None, request: str = "") -> List[str]:
    if output:
        values = []
        for part in output.replace(";", ",").split(","):
            v = part.strip().lower().replace("-", "_")
            if v == "quote":
                v = "quotation"
            if v in SUPPORTED_OUTPUTS:
                values.append(v)
        if values:
            return values
    r = request.lower()
    values = []
    if "invoice" in r:
        values.append("invoice")
    if "quote" in r or "quotation" in r or "offer" in r:
        values.append("quotation")
    if "margin" in r or "profit" in r or "underperform" in r:
        values.append("margin_analysis")
    if "production" in r or "location" in r or "volume split" in r or "capacity" in r or "plant" in r:
        values.append("production_optimization")
    if "compare" in r or "comparison" in r or "component" in r or "market" in r or "competitor" in r:
        values.append("product_comparison")
    if "schema" in r or "readiness" in r or "inspect" in r or "columns" in r:
        values.append("schema_report")
    if "scenario" in r or "sensitivity" in r or "what if" in r or "raw material" in r or "price shock" in r:
        values.append("scenario_analysis")
    if "why" in r or "explain" in r or "question" in r or "answer" in r:
        values.append("question_analysis")
    if "goal" in r or "find connections" in r or "keep finding" in r or "insight" in r or "connections" in r:
        values.append("goal_analysis")
    if "full" in r or "complete" in r or "management" in r or "executive" in r or "business report" in r:
        values.append("full_report")
    if not values:
        values = ["full_report"]
    # Remove duplicates preserving order.
    seen = set()
    return [v for v in values if not (v in seen or seen.add(v))]


def is_local_url(url: str) -> bool:
    u = (url or "").lower().strip()
    return u.startswith("http://localhost") or u.startswith("http://127.0.0.1") or u.startswith("http://[::1]")


def make_llm(args: argparse.Namespace) -> Optional[OllamaClient]:
    if not getattr(args, "ai", False):
        return None
    if getattr(args, "offline", False) and not is_local_url(getattr(args, "ollama_url", "")):
        return None
    return OllamaClient(model=getattr(args, "model", "qwen2.5:7b"), base_url=getattr(args, "ollama_url", "http://localhost:11434"))


def json_out(payload: Dict[str, Any], pretty: bool = True) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, default=str))


def inspect_files(args: argparse.Namespace) -> int:
    files = expand_files(args.files)
    result = {"ok": True, "files": [], "count": len(files)}
    for f in files:
        wb = apply_mapping_profile(read_workbook(str(f)), load_mapping_profile(getattr(args, "mapping", "")))
        products = extract_products(wb)
        result["files"].append({
            "path": str(f),
            "filename": wb.filename,
            "errors": wb.errors,
            "tables": wb.schema_summary(),
            "detected_product_rows": len(products),
            "sample_products": [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "location": p.location,
                    "unit_price": p.unit_price,
                    "unit_cost": p.total_cost(),
                    "margin_pct": p.margin_rate(),
                }
                for p in products[: args.sample_products]
            ],
        })
    json_out(result, pretty=not args.compact)
    return 0


def _report_output_path(out_dir: Path, file: Path, output: str) -> Path:
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in file.stem).strip("_") or "workbook"
    return out_dir / f"{safe_stem}_{output}.html"


def generate_output_for_workbook(wb, file: Path, output: str, args: argparse.Namespace, llm: Optional[OllamaClient]) -> Dict[str, Any]:
    out_dir = Path(getattr(args, "_resolved_out_dir", args.out_dir)).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = "quotation" if output == "quote" else output
    out_path = _report_output_path(out_dir, file, output)
    currency = args.currency
    if output == "margin_analysis":
        margin_analysis(wb, currency=currency, llm=llm, output_path=str(out_path))
    elif output == "production_optimization":
        production_optimization(wb, currency=currency, llm=llm, output_path=str(out_path))
    elif output == "product_comparison":
        product_comparison(wb, currency=currency, llm=llm, output_path=str(out_path))
    elif output == "schema_report":
        schema_report(wb, currency=currency, llm=llm, output_path=str(out_path))
    elif output == "scenario_analysis":
        scenario_analysis(wb, currency=currency, llm=llm, output_path=str(out_path))
    elif output == "question_analysis":
        question_analysis(wb, question=getattr(args, "question", "") or getattr(args, "request", ""), currency=currency, llm=llm, output_path=str(out_path), offline_mode=getattr(args, "offline", True))
    elif output == "goal_analysis":
        goal_analysis(wb, goal=getattr(args, "goal", "") or getattr(args, "question", "") or getattr(args, "request", ""), currency=currency, llm=llm, output_path=str(out_path), offline_mode=getattr(args, "offline", True))
    elif output in {"invoice", "quotation"}:
        products = extract_products(wb)
        quantities = parse_quantities(args.quantities)
        lines = selected_lines_from_products(products, select=args.select, quantities=quantities, default_qty=args.default_qty, max_lines=args.max_lines)
        if not lines:
            return {"output": output, "ok": False, "error": "No products selected/detected for document output"}
        template = args.template or ("quotation_basic" if output == "quotation" else "invoice_basic")
        render_document_template(
            wb,
            document_type=output,
            lines=lines,
            output_path=str(out_path),
            template_name=template,
            company=args.company,
            customer=args.customer,
            currency=currency,
            tax_rate=args.tax_rate,
            notes=args.notes,
            user_template_dir=args.template_dir,
            extra={"request": getattr(args, "request", "")},
        )
    else:
        full_report(wb, currency=currency, llm=llm, output_path=str(out_path))
    export_result = export_html(str(out_path), parse_formats(getattr(args, "formats", "html")))
    return {"output": output, "ok": True and export_result.get("ok", True), "path": str(out_path), "exports": export_result}


def batch(args: argparse.Namespace) -> int:
    files = expand_files(args.files)
    if not files:
        json_out({"ok": False, "error": "No input Excel/CSV files found", "files": []})
        return 2
    outputs = parse_outputs(args.output, args.request)
    llm = make_llm(args)
    label = args.session_label or (outputs[0] if outputs else "batch")
    if args.flat_output:
        resolved_out_dir = Path(args.out_dir).expanduser().resolve()
        resolved_out_dir.mkdir(parents=True, exist_ok=True)
    else:
        resolved_out_dir = session_output_dir(args.out_dir, label=label, session_id=args.session_id or None)
    setattr(args, "_resolved_out_dir", str(resolved_out_dir))
    result = {"ok": True, "request": args.request, "outputs_requested": outputs, "formats": parse_formats(args.formats), "session_dir": str(resolved_out_dir), "files": []}
    for f in files:
        wb = apply_mapping_profile(read_workbook(str(f)), load_mapping_profile(getattr(args, "mapping", "")))
        file_result = {"path": str(f), "filename": wb.filename, "errors": wb.errors, "outputs": []}
        if not wb.tables:
            file_result["ok"] = False
            file_result["error"] = "No readable tables"
            result["files"].append(file_result)
            continue
        for output in outputs:
            try:
                file_result["outputs"].append(generate_output_for_workbook(wb, f, output, args, llm))
            except Exception as exc:
                file_result["outputs"].append({"output": output, "ok": False, "error": str(exc)})
                result["ok"] = False
        file_result["ok"] = all(o.get("ok") for o in file_result["outputs"])
        if args.audit:
            try:
                file_result["audit_record"] = create_audit_record([str(f)], vars(args), file_result["outputs"], base_dir=args.audit_dir or None)
            except Exception as audit_exc:
                file_result["audit_error"] = str(audit_exc)
        result["files"].append(file_result)
    json_out(result, pretty=not args.compact)
    return 0 if result["ok"] else 1


def parse_quantities(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        if raw.startswith("{"):
            return json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Invalid quantities JSON: {exc}")
    out: Dict[str, Any] = {}
    for part in raw.split(","):
        if not part.strip():
            continue
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        out[key.strip()] = safe_number(val.strip(), 1.0)
    return out


def document(args: argparse.Namespace) -> int:
    f = expand_files([args.file])
    if not f:
        json_out({"ok": False, "error": f"File not found: {args.file}"})
        return 2
    file = f[0]
    wb = apply_mapping_profile(read_workbook(str(file)), load_mapping_profile(getattr(args, "mapping", "")))
    products = extract_products(wb)
    quantities = parse_quantities(args.quantities)
    lines = selected_lines_from_products(products, select=args.select, quantities=quantities, default_qty=args.default_qty, max_lines=args.max_lines)
    if not lines:
        json_out({"ok": False, "error": "No products selected/detected", "detected_product_rows": len(products)})
        return 1
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        session_dir_value = str(out_path.parent)
    else:
        if args.flat_output:
            doc_out_dir = Path(args.out_dir).expanduser().resolve()
            doc_out_dir.mkdir(parents=True, exist_ok=True)
        else:
            doc_out_dir = session_output_dir(args.out_dir, label=args.session_label or args.type, session_id=args.session_id or None)
        session_dir_value = str(doc_out_dir)
        out_path = _report_output_path(doc_out_dir, file, args.type)
    template = args.template or ("quotation_basic" if args.type == "quotation" else "invoice_basic")
    path = render_document_template(
        wb,
        document_type=args.type,
        lines=lines,
        output_path=str(out_path),
        template_name=template,
        company=args.company,
        customer=args.customer,
        currency=args.currency,
        tax_rate=args.tax_rate,
        notes=args.notes,
        user_template_dir=args.template_dir,
        extra={"selected_line_count": len(lines)},
    )
    export_result = export_html(path, parse_formats(args.formats))
    payload = {"ok": export_result.get("ok", True), "path": path, "template": template, "lines": len(lines), "source_file": str(file), "session_dir": session_dir_value, "exports": export_result}
    if args.audit:
        try:
            payload["audit_record"] = create_audit_record([str(file)], vars(args), [payload], base_dir=args.audit_dir or None)
        except Exception as audit_exc:
            payload["audit_error"] = str(audit_exc)
    json_out(payload, pretty=not args.compact)
    return 0 if payload["ok"] else 1


def mappings(args: argparse.Namespace) -> int:
    if args.mapping_action == "example":
        path = write_example_mapping(args.out)
        json_out({"ok": True, "path": path, "message": "Edit this mapping profile and pass it with --mapping."}, pretty=not args.compact)
        return 0
    json_out({"ok": False, "error": f"Unknown mapping action: {args.mapping_action}"})
    return 2


def templates(args: argparse.Namespace) -> int:
    action = args.template_action
    if action == "list":
        json_out({"ok": True, "templates": [t.__dict__ for t in list_templates(args.template_dir)]}, pretty=not args.compact)
        return 0
    if action == "show":
        print(read_template(args.name, args.template_dir))
        return 0
    if action == "create":
        path = create_template(args.name, from_template=args.from_template, user_template_dir=args.template_dir, overwrite=args.overwrite)
        json_out({"ok": True, "path": str(path), "message": "Template created. Edit this file, then use it by name with --template."})
        return 0
    if action == "update":
        path = update_template(args.name, args.file, user_template_dir=args.template_dir, overwrite=True)
        json_out({"ok": True, "path": str(path), "message": "Template updated."})
        return 0
    if action == "delete":
        path = delete_user_template(args.name, args.template_dir)
        json_out({"ok": True, "deleted": str(path)})
        return 0
    if action == "context":
        files = expand_files([args.file])
        if not files:
            json_out({"ok": False, "error": f"File not found: {args.file}"})
            return 2
        wb = apply_mapping_profile(read_workbook(str(files[0])), load_mapping_profile(getattr(args, "mapping", "")))
        products = extract_products(wb)
        lines = selected_lines_from_products(products, select=args.select, quantities=parse_quantities(args.quantities), default_qty=args.default_qty, max_lines=args.max_lines)
        context = make_document_context(wb, args.type, lines, company=args.company, customer=args.customer, currency=args.currency, tax_rate=args.tax_rate, notes=args.notes)
        if args.out:
            out = Path(args.out).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(context_json_preview(context), encoding="utf-8")
            json_out({"ok": True, "path": str(out)})
        else:
            print(context_json_preview(context))
        return 0
    json_out({"ok": False, "error": f"Unknown template action: {action}"})
    return 2


def parse_formats(raw: str | Sequence[str] | None) -> List[str]:
    if raw is None:
        return ["html"]
    if isinstance(raw, str):
        parts = raw.replace(";", ",").split(",")
    else:
        parts = list(raw)
    out = []
    for part in parts:
        p = str(part).strip().lower()
        if not p:
            continue
        if p == "word":
            p = "docx"
        if p in {"html", "pdf", "docx"} and p not in out:
            out.append(p)
    return out or ["html"]


def insights(args: argparse.Namespace) -> int:
    if args.insight_action == "list":
        queue = load_review_queue(args.session_dir)
        state = load_goal_state(args.session_dir)
        json_out({"ok": True, "session_dir": str(Path(args.session_dir).expanduser().resolve()), "queue": queue, "goal_state": state}, pretty=not args.compact)
        return 0
    if args.insight_action == "set-status":
        queue = set_insight_status(args.session_dir, args.id, args.status, notes=args.notes)
        json_out({"ok": True, "session_dir": str(Path(args.session_dir).expanduser().resolve()), "queue": queue}, pretty=not args.compact)
        return 0
    json_out({"ok": False, "error": f"Unknown insight action: {args.insight_action}"})
    return 2


def approvals(args: argparse.Namespace) -> int:
    if args.approval_action == "list":
        json_out({"ok": True, "register": load_approval_register(args.audit_dir or None)}, pretty=not args.compact)
        return 0
    if args.approval_action == "set-status":
        reg = set_output_status(args.path, args.status, notes=args.notes, base_dir=args.audit_dir or None)
        json_out({"ok": True, "register": reg}, pretty=not args.compact)
        return 0
    json_out({"ok": False, "error": f"Unknown approval action: {args.approval_action}"})
    return 2


def add_common_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--currency", default="€", help="Currency symbol, default €")
    parser.add_argument("--ai", action="store_true", help="Use local Ollama for narrative commentary")
    parser.add_argument("--model", default="qwen2.5:7b", help="Local Ollama model name")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Local Ollama base URL")
    parser.add_argument("--offline", action="store_true", default=False, help="Data-security mode: no external APIs/web; only local files and localhost Ollama are allowed")
    parser.add_argument("--out-dir", default="generated", help="Base directory for generated files. By default each run creates a dated session subfolder inside it.")
    parser.add_argument("--session-id", default="", help="Optional fixed session folder name. Defaults to date_time_label_random.")
    parser.add_argument("--session-label", default="", help="Optional label included in the generated session folder name.")
    parser.add_argument("--flat-output", action="store_true", help="Disable dated session subfolder and write directly to --out-dir. Not recommended for normal runs.")
    parser.add_argument("--formats", default="html", help="Comma-separated export formats: html,pdf,docx")
    parser.add_argument("--audit", action="store_true", help="Write audit/provenance record and draft approval entries")
    parser.add_argument("--audit-dir", default="", help="Base directory for audit registry, default home")
    parser.add_argument("--compact", action="store_true", help="Compact JSON output")


def add_document_args(parser: argparse.ArgumentParser, include_file: bool = False) -> None:
    if include_file:
        parser.add_argument("--file", required=True, help="Input Excel/CSV file")
    parser.add_argument("--type", choices=["invoice", "quotation"], default="invoice", help="Document type")
    parser.add_argument("--template", default="", help="Template name, e.g. invoice_basic or a user template")
    parser.add_argument("--template-dir", default=os.environ.get("BUSINESS_AI_TEMPLATE_DIR", ""), help="User template directory")
    parser.add_argument("--company", default="Your Company")
    parser.add_argument("--customer", default="Customer")
    parser.add_argument("--tax-rate", type=float, default=21.0)
    parser.add_argument("--notes", default="")
    parser.add_argument("--select", default="all", help="Product selection: all, top-margin, positive-margin, ids:0,1, sku:A-100,B-200, or comma-separated IDs/SKUs")
    parser.add_argument("--quantities", default="", help="Quantities as JSON {'SKU': 10} or comma list SKU:10,ID:2")
    parser.add_argument("--default-qty", type=float, default=1.0)
    parser.add_argument("--max-lines", type=int, default=200)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent skill CLI for Excel/CSV business process automation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Inspect workbook schemas and detected product rows")
    p_inspect.add_argument("--files", nargs="+", required=True, help="Files, directories, or glob patterns")
    p_inspect.add_argument("--sample-products", type=int, default=10)
    p_inspect.add_argument("--mapping", default="", help="Optional JSON/YAML manual column mapping profile")
    p_inspect.add_argument("--compact", action="store_true")
    p_inspect.set_defaults(func=inspect_files)

    p_batch = sub.add_parser("batch", help="Generate one or more outputs for a list of workbooks")
    p_batch.add_argument("--files", nargs="+", required=True, help="Files, directories, or glob patterns")
    p_batch.add_argument("--output", default="", help="Comma-separated outputs: invoice,quotation,full_report,margin_analysis,production_optimization,product_comparison,scenario_analysis,schema_report")
    p_batch.add_argument("--request", default="", help="Natural-language request used to infer outputs when --output is omitted")
    p_batch.add_argument("--question", default="", help="Ad-hoc business question for question_analysis output")
    p_batch.add_argument("--goal", default="", help="Goal for goal_analysis insight mining output")
    p_batch.add_argument("--mapping", default="", help="Optional JSON/YAML manual column mapping profile")
    add_common_generation_args(p_batch)
    add_document_args(p_batch, include_file=False)
    p_batch.set_defaults(func=batch)

    p_doc = sub.add_parser("document", help="Generate an invoice or quotation from one workbook")
    add_common_generation_args(p_doc)
    add_document_args(p_doc, include_file=True)
    p_doc.add_argument("--out", default="", help="Specific output HTML path")
    p_doc.add_argument("--mapping", default="", help="Optional JSON/YAML manual column mapping profile")
    p_doc.add_argument("--question", default="", help="Unused for documents; accepted for harness compatibility")
    p_doc.set_defaults(func=document)

    p_tpl = sub.add_parser("templates", help="List, create, show, update and delete document templates")
    tpl_sub = p_tpl.add_subparsers(dest="template_action", required=True)

    p_tpl_list = tpl_sub.add_parser("list", help="List templates")
    p_tpl_list.add_argument("--template-dir", default=os.environ.get("BUSINESS_AI_TEMPLATE_DIR", ""))
    p_tpl_list.add_argument("--compact", action="store_true")
    p_tpl_list.set_defaults(func=templates)

    p_tpl_show = tpl_sub.add_parser("show", help="Print a template")
    p_tpl_show.add_argument("--name", required=True)
    p_tpl_show.add_argument("--template-dir", default=os.environ.get("BUSINESS_AI_TEMPLATE_DIR", ""))
    p_tpl_show.set_defaults(func=templates)

    p_tpl_create = tpl_sub.add_parser("create", help="Create a user-editable template by copying an existing template")
    p_tpl_create.add_argument("--name", required=True)
    p_tpl_create.add_argument("--from-template", default="invoice_basic")
    p_tpl_create.add_argument("--template-dir", default=os.environ.get("BUSINESS_AI_TEMPLATE_DIR", ""))
    p_tpl_create.add_argument("--overwrite", action="store_true")
    p_tpl_create.set_defaults(func=templates)

    p_tpl_update = tpl_sub.add_parser("update", help="Replace/save a user template from a file")
    p_tpl_update.add_argument("--name", required=True)
    p_tpl_update.add_argument("--file", required=True)
    p_tpl_update.add_argument("--template-dir", default=os.environ.get("BUSINESS_AI_TEMPLATE_DIR", ""))
    p_tpl_update.set_defaults(func=templates)

    p_tpl_delete = tpl_sub.add_parser("delete", help="Delete a user template")
    p_tpl_delete.add_argument("--name", required=True)
    p_tpl_delete.add_argument("--template-dir", default=os.environ.get("BUSINESS_AI_TEMPLATE_DIR", ""))
    p_tpl_delete.set_defaults(func=templates)

    p_tpl_context = tpl_sub.add_parser("context", help="Generate JSON context preview for template editing")
    add_document_args(p_tpl_context, include_file=True)
    p_tpl_context.add_argument("--currency", default="€")
    p_tpl_context.add_argument("--out", default="", help="Write context JSON to file instead of stdout")
    p_tpl_context.add_argument("--mapping", default="", help="Optional JSON/YAML manual column mapping profile")
    p_tpl_context.set_defaults(func=templates)

    p_mapping = sub.add_parser("mappings", help="Create mapping profile examples for manual column mapping")
    map_sub = p_mapping.add_subparsers(dest="mapping_action", required=True)
    p_map_ex = map_sub.add_parser("example", help="Write an example JSON mapping profile")
    p_map_ex.add_argument("--out", default="mapping_example.json")
    p_map_ex.add_argument("--compact", action="store_true")
    p_map_ex.set_defaults(func=mappings)

    p_insights = sub.add_parser("insights", help="List or review insights in a session folder")
    ins_sub = p_insights.add_subparsers(dest="insight_action", required=True)
    p_ins_list = ins_sub.add_parser("list", help="List scored insights and goal state for a session folder")
    p_ins_list.add_argument("--session-dir", required=True)
    p_ins_list.add_argument("--compact", action="store_true")
    p_ins_list.set_defaults(func=insights)
    p_ins_set = ins_sub.add_parser("set-status", help="Accept/reject/update an insight in the manual review queue")
    p_ins_set.add_argument("--session-dir", required=True)
    p_ins_set.add_argument("--id", required=True, help="Insight ID")
    p_ins_set.add_argument("--status", required=True, choices=["new", "reviewing", "accepted", "rejected", "needs_more_data", "converted_to_action"])
    p_ins_set.add_argument("--notes", default="")
    p_ins_set.add_argument("--compact", action="store_true")
    p_ins_set.set_defaults(func=insights)

    p_approval = sub.add_parser("approvals", help="List or update draft/review/approval status for generated files")
    appr_sub = p_approval.add_subparsers(dest="approval_action", required=True)
    p_appr_list = appr_sub.add_parser("list", help="List approval register")
    p_appr_list.add_argument("--audit-dir", default="")
    p_appr_list.add_argument("--compact", action="store_true")
    p_appr_list.set_defaults(func=approvals)
    p_appr_set = appr_sub.add_parser("set-status", help="Set status for an output path")
    p_appr_set.add_argument("--path", required=True)
    p_appr_set.add_argument("--status", required=True, choices=["draft", "reviewed", "approved", "sent", "rejected", "revised"])
    p_appr_set.add_argument("--notes", default="")
    p_appr_set.add_argument("--audit-dir", default="")
    p_appr_set.add_argument("--compact", action="store_true")
    p_appr_set.set_defaults(func=approvals)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        eprint("Interrupted")
        return 130
    except Exception as exc:
        json_out({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
