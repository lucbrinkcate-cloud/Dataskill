from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, Response, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from core.business_logic import (
    extract_products,
    full_report,
    generate_selected_document_from_form,
    margin_analysis,
    product_comparison,
    product_options_html,
    production_optimization,
    schema_report,
)
from core.excel_reader import read_workbook
from core.html_renderer import DEFAULT_STYLE, card, esc
from core.llm import OllamaClient

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"
UPLOAD_DIR.mkdir(exist_ok=True)
GENERATED_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"xlsx", "xlsm", "xltx", "xltm", "xls", "csv"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB local default


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def app_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{DEFAULT_STYLE}
.form-grid {{ display:grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }}
.field {{ grid-column: span 6; }}
.field.full {{ grid-column: span 12; }}
label {{ display:block; font-size:13px; color:#344054; font-weight:700; margin-bottom:6px; }}
input, select, textarea {{ width:100%; border:1px solid var(--line); border-radius:12px; padding:11px 12px; font:inherit; background:#fff; }}
textarea {{ min-height:90px; }}
button, .button {{ display:inline-flex; border:0; border-radius:12px; padding:11px 16px; font-weight:800; color:#fff; background:var(--primary); text-decoration:none; cursor:pointer; }}
.button.secondary {{ background:#0e7c86; }}
.button.ghost {{ background:#fff; color:var(--primary); border:1px solid var(--line); }}
.help {{ color:var(--muted); font-size:12px; margin-top:5px; }}
@media(max-width:760px){{ .field {{ grid-column: span 12; }} }}
</style>
</head>
<body>
<header class="hero">
  <h1>{esc(title)}</h1>
  <p>Upload any Excel/CSV workbook, choose the business process output, and generate a self-contained HTML result.</p>
</header>
<main>{body}</main>
</body>
</html>"""


def llm_from_request() -> Optional[OllamaClient]:
    use_ai = request.form.get("use_ai", "") == "yes"
    if not use_ai:
        return None
    model = request.form.get("model", "qwen2.5:7b") or "qwen2.5:7b"
    base_url = request.form.get("ollama_url", "http://localhost:11434") or "http://localhost:11434"
    return OllamaClient(model=model, base_url=base_url)


def output_filename(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}.html"


@app.get("/")
def index() -> str:
    body = card("Start a run", f"""
    <form method="post" action="{url_for('upload')}" enctype="multipart/form-data">
      <div class="form-grid">
        <div class="field full">
          <label for="file">Excel or CSV file</label>
          <input id="file" name="file" type="file" accept=".xlsx,.xlsm,.xls,.csv" required>
          <div class="help">The tool scans sheets and columns automatically. No fixed workbook structure is required, but results improve when columns contain clear names like product, SKU, price, cost, location, quantity, capacity, handling, labor, material, market/competitor.</div>
        </div>
        <div class="field">
          <label for="output_type">What output do you want?</label>
          <select id="output_type" name="output_type" required>
            <option value="invoice">Invoice draft: select items and quantities</option>
            <option value="quotation">Quotation draft: select items and quantities</option>
            <option value="full_report">Full business HTML report</option>
            <option value="margin_analysis">Margin analysis</option>
            <option value="production_optimization">Production location/volume optimization</option>
            <option value="product_comparison">Product/component/market comparison</option>
            <option value="schema_report">Workbook schema/readiness report</option>
          </select>
        </div>
        <div class="field">
          <label for="currency">Currency symbol</label>
          <input id="currency" name="currency" value="€" maxlength="5">
        </div>
        <div class="field">
          <label for="use_ai">Local AI model</label>
          <select id="use_ai" name="use_ai">
            <option value="yes" selected>Use local Ollama model if running</option>
            <option value="no">Do not use AI; only deterministic calculations</option>
          </select>
          <div class="help">The file stays on your machine. AI calls go to your local Ollama URL.</div>
        </div>
        <div class="field">
          <label for="model">Model name</label>
          <input id="model" name="model" value="qwen2.5:7b" placeholder="qwen2.5:7b, gemma3:12b, llama3.1:8b...">
        </div>
        <div class="field full">
          <label for="ollama_url">Ollama URL</label>
          <input id="ollama_url" name="ollama_url" value="http://localhost:11434">
          <div class="help">Example setup: install Ollama, run <code>ollama pull qwen2.5:7b</code>, then keep Ollama running.</div>
        </div>
        <div class="field full">
          <button type="submit">Read workbook and continue</button>
        </div>
      </div>
    </form>
    """)
    body += card("What this MVP can generate", """
    <ul>
      <li><strong>Invoice / quotation:</strong> after upload the app shows detected products/items; user selects line items, quantities and optional override prices.</li>
      <li><strong>Margin analysis:</strong> strongest and weakest products, estimated profit, cost drivers, improvement ideas.</li>
      <li><strong>Production optimization:</strong> compares production locations using detected cost, demand, handling and capacity data, then recommends a volume split.</li>
      <li><strong>Product/component comparison:</strong> compares products sold by the company and uses market/competitor sheets if present.</li>
      <li><strong>HTML output:</strong> every result is a standalone HTML file saved in the <code>generated/</code> folder.</li>
    </ul>
    """)
    return app_page("Local Business AI Tool", body)


@app.post("/upload")
def upload() -> str:
    file = request.files.get("file")
    if not file or not file.filename:
        return app_page("Upload error", card("Missing file", "<p class='warn'>Please choose an Excel or CSV file.</p><p><a class='button ghost' href='/'>Back</a></p>"))
    if not allowed_file(file.filename):
        return app_page("Upload error", card("Unsupported file", "<p class='warn'>Use .xlsx, .xlsm, .xls or .csv.</p><p><a class='button ghost' href='/'>Back</a></p>"))

    safe_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex[:10]}_{safe_name}"
    path = UPLOAD_DIR / stored_name
    file.save(path)

    output_type = request.form.get("output_type", "full_report")
    currency = request.form.get("currency", "€") or "€"
    model = request.form.get("model", "qwen2.5:7b")
    ollama_url = request.form.get("ollama_url", "http://localhost:11434")
    use_ai = request.form.get("use_ai", "yes")

    workbook = read_workbook(str(path))
    if workbook.errors and not workbook.tables:
        return app_page("Workbook error", card("Could not read workbook", f"<div class='warn'>{esc(chr(10).join(workbook.errors))}</div><p><a class='button ghost' href='/'>Back</a></p>"))

    if output_type in {"invoice", "quotation"}:
        products = extract_products(workbook)
        roles_rows = []
        for t in workbook.tables[:8]:
            roles = ", ".join(f"{r}: {m.column}" for r, m in (t.schema.roles.items() if t.schema else []))
            roles_rows.append(f"<li><strong>{esc(t.name)}</strong> — {t.rows} rows · {esc(roles or 'no roles detected')}</li>")
        body = card(f"Select items for {output_type}", f"""
        <form method="post" action="{url_for('generate_document')}">
          <input type="hidden" name="file_id" value="{esc(stored_name)}">
          <input type="hidden" name="document_type" value="{esc(output_type)}">
          <input type="hidden" name="currency" value="{esc(currency)}">
          <input type="hidden" name="use_ai" value="{esc(use_ai)}">
          <input type="hidden" name="model" value="{esc(model)}">
          <input type="hidden" name="ollama_url" value="{esc(ollama_url)}">
          <div class="form-grid">
            <div class="field"><label>Company name</label><input name="company" value="Your Company"></div>
            <div class="field"><label>Customer name</label><input name="customer" value="Customer"></div>
            <div class="field"><label>Tax/VAT %</label><input name="tax_rate" type="number" step="0.01" value="21"></div>
            <div class="field"><label>Currency</label><input value="{esc(currency)}" disabled></div>
            <div class="field full"><label>Notes / terms</label><textarea name="notes" placeholder="Payment terms, delivery terms, validity, special conditions..."></textarea></div>
          </div>
          <h3>Detected line items</h3>
          {product_options_html(products, currency=currency)}
          <p style="margin-top:16px"><button type="submit">Generate {esc(output_type.title())} HTML</button> <a class="button ghost" href="/">Cancel</a></p>
        </form>
        """)
        body += card("Detected workbook roles", "<ul>" + "".join(roles_rows) + "</ul>" + (f"<div class='warn'>{esc(chr(10).join(workbook.errors))}</div>" if workbook.errors else ""))
        return app_page(f"Prepare {output_type.title()}", body)

    llm = OllamaClient(model=model, base_url=ollama_url) if use_ai == "yes" else None
    prefix = output_type
    out_name = output_filename(prefix)
    out_path = GENERATED_DIR / out_name

    if output_type == "margin_analysis":
        margin_analysis(workbook, currency=currency, llm=llm, output_path=str(out_path))
    elif output_type == "production_optimization":
        production_optimization(workbook, currency=currency, llm=llm, output_path=str(out_path))
    elif output_type == "product_comparison":
        product_comparison(workbook, currency=currency, llm=llm, output_path=str(out_path))
    elif output_type == "schema_report":
        schema_report(workbook, currency=currency, llm=llm, output_path=str(out_path))
    else:
        full_report(workbook, currency=currency, llm=llm, output_path=str(out_path))

    return result_page(out_name, output_type)


@app.post("/generate-document")
def generate_document() -> str:
    file_id = secure_filename(request.form.get("file_id", ""))
    path = UPLOAD_DIR / file_id
    if not file_id or not path.exists():
        return app_page("File not found", card("Missing uploaded file", "<p class='warn'>The uploaded file could not be found. Please start again.</p><p><a class='button ghost' href='/'>Back</a></p>"))
    workbook = read_workbook(str(path))
    document_type = request.form.get("document_type", "invoice")
    currency = request.form.get("currency", "€") or "€"
    use_ai = request.form.get("use_ai", "yes")
    model = request.form.get("model", "qwen2.5:7b")
    ollama_url = request.form.get("ollama_url", "http://localhost:11434")
    llm = OllamaClient(model=model, base_url=ollama_url) if use_ai == "yes" else None
    out_name = output_filename(document_type)
    out_path = GENERATED_DIR / out_name
    generate_selected_document_from_form(workbook, request.form, document_type=document_type, currency=currency, llm=llm, output_path=str(out_path))
    return result_page(out_name, document_type)


def result_page(out_name: str, output_type: str) -> str:
    link = url_for("generated_file", filename=out_name)
    body = card("HTML output ready", f"""
    <p>{esc(output_type.replace('_', ' ').title())} has been generated.</p>
    <p><a class="button" href="{link}" target="_blank">Open HTML output</a> <a class="button secondary" href="{link}" download>Download HTML</a> <a class="button ghost" href="/">Start another run</a></p>
    <p class="small">Saved locally as <code>generated/{esc(out_name)}</code>.</p>
    <iframe src="{link}" style="width:100%;height:680px;border:1px solid var(--line);border-radius:16px;background:white"></iframe>
    """)
    return app_page("Output generated", body)


@app.get("/generated/<path:filename>")
def generated_file(filename: str):
    return send_from_directory(GENERATED_DIR, filename, as_attachment=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"\nLocal Business AI Tool running at http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
