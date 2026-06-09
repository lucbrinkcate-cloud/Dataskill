from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

CONFIG_DIR = Path.home() / ".business_ai_skill"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "first_run_complete": False,
    "company": {
        "name": "Your Company",
        "address": "Company address placeholder",
        "vat_number": "VAT number placeholder",
        "bank": "Bank/IBAN placeholder",
        "email": "sales@example.com",
        "phone": "Phone placeholder",
    },
    "defaults": {
        "currency": "€",
        "tax_rate": 21.0,
        "output_dir": "generated/dashboard_runs",
        "formats": ["html", "pdf", "docx"],
        "outputs": ["full_report", "margin_analysis", "production_optimization", "product_comparison", "scenario_analysis"],
        "document_select": "positive-margin",
        "default_qty": 1.0,
        "max_lines": 200,
    },
    "ai": {
        "use_ai": True,
        "provider": "ollama",
        "model": "qwen2.5:7b",
        "ollama_url": "http://localhost:11434",
    },
    "templates": {
        "invoice": "invoice_basic",
        "quotation": "quotation_basic",
        "template_dir": "",
    },
    "workflow": {
        "always_plan_first": True,
        "require_confirmation": True,
        "write_audit_trail": True,
        "approval_workflow": True,
        "offline_mode": True,
    },
    "connectors": {
        "uploaded_market_files": True,
        "agent_web_research": True,
        "supplier_api": False,
        "erp_accounting": False,
        "connector_notes": "Configure APIs/credentials later. Uploaded competitor/market workbooks work now.",
    },
}


def deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return deep_merge(DEFAULT_CONFIG, loaded)
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(config: Dict[str, Any]) -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = deep_merge(DEFAULT_CONFIG, config)
    CONFIG_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(CONFIG_PATH)


def update_from_form(form: Any) -> Dict[str, Any]:
    def get(name: str, default: str = "") -> str:
        return str(form.get(name, default) or default)

    formats = form.getlist("formats") if hasattr(form, "getlist") else []
    outputs = form.getlist("outputs") if hasattr(form, "getlist") else []
    try:
        tax_rate = float(get("tax_rate", "21"))
    except Exception:
        tax_rate = 21.0
    cfg = load_config()
    cfg["first_run_complete"] = True
    cfg["company"] = {
        "name": get("company_name", "Your Company"),
        "address": get("company_address", "Company address placeholder"),
        "vat_number": get("vat_number", "VAT number placeholder"),
        "bank": get("bank", "Bank/IBAN placeholder"),
        "email": get("email", "sales@example.com"),
        "phone": get("phone", "Phone placeholder"),
    }
    cfg["defaults"].update({
        "currency": get("currency", "€"),
        "tax_rate": tax_rate,
        "output_dir": get("output_dir", "generated/dashboard_runs"),
        "formats": formats or ["html", "pdf", "docx"],
        "outputs": outputs or ["full_report"],
        "document_select": get("document_select", "positive-margin"),
    })
    cfg["ai"].update({
        "use_ai": get("use_ai", "yes") == "yes",
        "model": get("model", "qwen2.5:7b"),
        "ollama_url": get("ollama_url", "http://localhost:11434"),
    })
    cfg["templates"].update({
        "invoice": get("invoice_template", "invoice_basic"),
        "quotation": get("quotation_template", "quotation_basic"),
        "template_dir": get("template_dir", ""),
    })
    cfg["workflow"].update({
        "always_plan_first": True,
        "require_confirmation": True,
        "write_audit_trail": get("audit", "yes") == "yes",
        "approval_workflow": get("approval", "yes") == "yes",
        "offline_mode": get("offline_mode", "yes") == "yes",
    })
    cfg["connectors"].update({
        "uploaded_market_files": "uploaded_market_files" in form if hasattr(form, "__contains__") else True,
        "agent_web_research": "agent_web_research" in form if hasattr(form, "__contains__") else True,
        "supplier_api": "supplier_api" in form if hasattr(form, "__contains__") else False,
        "erp_accounting": "erp_accounting" in form if hasattr(form, "__contains__") else False,
        "connector_notes": get("connector_notes", ""),
    })
    save_config(cfg)
    return cfg
