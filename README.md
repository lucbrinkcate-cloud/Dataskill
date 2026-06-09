# Local Business AI Tool — Excel/CSV to HTML Business Outputs

This is a working MVP plus an installable agent skill for a local AI-assisted business process automation tool.

It lets a user upload an existing Excel/CSV file, choose the desired output at the start of the run, and generate a standalone HTML file with visual support.

## Current outputs

1. **Invoice draft**
   - Upload workbook
   - Tool detects product/item rows
   - User selects line items, quantity and optional override unit price
   - Generates a print-friendly HTML invoice

2. **Quotation draft**
   - Same workflow as invoice
   - Adds quote validity/payment note structure

3. **Full business report**
   - Executive KPIs
   - Product margins
   - Production location cost comparison
   - Product/component group comparison
   - Workbook schema detection
   - Optional local AI executive recommendations

4. **Margin analysis**
   - Identifies strongest and weakest margin products
   - Estimates profit using detected quantity/demand
   - Suggests improvement angles for underperforming margins

5. **Production optimization**
   - Compares production locations/plants/countries/sites
   - Uses detected unit cost or cost components
   - Uses demand/quantity and capacity where available
   - Recommends a volume split by location

6. **Product/component/market comparison**
   - Compares internal products and components
   - Uses market/competitor sheets if the workbook contains them
   - Notes when current market data is missing

7. **Workbook schema/readiness report**
   - Shows detected sheets, columns and inferred business roles
   - Useful when the workbook structure is messy or unknown

## Important design choice

You said you cannot promise a fixed workbook structure. This tool therefore scans arbitrary workbooks and tries to infer column roles from headers and sample values.

It looks for roles such as:

- SKU / item code
- product / description / component / material
- category / product group
- quantity / demand / production volume
- unit price / sales price
- unit cost / production cost / landed cost
- raw material, labor/labour, handling/logistics, overhead
- location / country / plant / factory / site
- capacity
- supplier / customer
- competitor / market benchmark

The more descriptive the workbook headers are, the better the output will be.

## Local AI integration

The app can use a locally downloaded model through **Ollama**.

Examples of local models you can try if available in your Ollama installation:

- `qwen2.5:7b`
- `qwen2.5:14b`
- `gemma3:12b`
- `llama3.1:8b`
- Any future/new model that Ollama exposes through the same API

The model name is editable in the web form, so you can use newer Gemma/Qwen models when they are released and supported locally.

By default the app sends AI prompts only to:

```text
http://localhost:11434
```

That means your workbook data stays on your machine unless you deliberately point the URL somewhere else.

## Install

From this folder:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional local AI setup:

```bash
# Install Ollama from https://ollama.com first, then:
ollama pull qwen2.5:7b
ollama serve
```

If Ollama is already running as a background service, you do not need `ollama serve`.

## Run the browser app

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Workflow:

1. Choose the HTML output type.
2. Upload `.xlsx`, `.xlsm`, `.xls` or `.csv`.
3. Choose currency and local AI model options.
4. For invoices/quotations, select items and quantities after the workbook is read.
5. Open or download the generated HTML output.

Generated files are saved in:

```text
generated/
```

Uploaded files are saved locally in:

```text
uploads/
```

## Install as an agent skill

The project now includes a portable SKILL.md-style agent skill:

```text
agent_skill/business-process-excel-analyst/
```

Install it into Hermes:

```bash
python install_agent_skill.py --target hermes --force
```

This copies the skill to:

```text
~/.hermes/skills/business-process-excel-analyst
```

It also writes an `engine_path.txt` file so the copied skill can find this local Python engine.

Install it for Claude Code-style skills:

```bash
python install_agent_skill.py --target claude --force
```

Install it for OpenAI/Codex-style agent skills:

```bash
python install_agent_skill.py --target codex --force
```

Install to any custom harness skill directory:

```bash
python install_agent_skill.py --target custom --path /path/to/skills/business-process-excel-analyst --force
```

You can also avoid copying by setting:

```bash
export BUSINESS_AI_HOME=/absolute/path/to/local_business_ai
```

Then an agent can run the wrapper directly:

```bash
python agent_skill/business-process-excel-analyst/scripts/business_excel_skill.py inspect --files "data/*.xlsx"
```

### Agent skill examples

Inspect a folder/list of Excel files:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py inspect --files "data/*.xlsx"
```

Generate outputs from a natural-language request:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py batch \
  --files "data/*.xlsx" \
  --request "make a full business report, margin analysis, and production location recommendation" \
  --out-dir outputs
```

Generate several deterministic outputs:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py batch \
  --files "data/*.xlsx" \
  --output full_report,margin_analysis,production_optimization,product_comparison \
  --out-dir outputs
```

Generate an invoice from selected SKUs:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py document \
  --file workbook.xlsx \
  --type invoice \
  --select sku:A-100,B-200 \
  --quantities 'A-100:10,B-200:5' \
  --company "Seller BV" \
  --customer "Buyer BV" \
  --out outputs/invoice.html
```

### Template management

List templates:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py templates list
```

Create a saved editable invoice template:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py templates create \
  --name acme_invoice \
  --from-template invoice_basic
```

Show/edit the template source:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py templates show --name acme_invoice
```

Generate context JSON for template design:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py templates context \
  --file workbook.xlsx \
  --type invoice \
  --select all \
  --out context.json
```

Save an edited template:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py templates update \
  --name acme_invoice \
  --file edited_invoice.html.j2
```

Use the saved template:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py document \
  --file workbook.xlsx \
  --type invoice \
  --template acme_invoice \
  --select all
```

User templates are saved by default in:

```text
~/.business_ai_skill/templates
```

Set `BUSINESS_AI_TEMPLATE_DIR` if you want a project-specific template folder.

## Run from command line

Generate a full report:

```bash
python run_cli.py path/to/your_file.xlsx --output full_report --currency "€"
```

Generate a margin analysis:

```bash
python run_cli.py path/to/your_file.xlsx --output margin_analysis --currency "€"
```

Generate production optimization:

```bash
python run_cli.py path/to/your_file.xlsx --output production_optimization --currency "€"
```

Generate product comparison:

```bash
python run_cli.py path/to/your_file.xlsx --output product_comparison --currency "€"
```

Generate with local AI commentary:

```bash
python run_cli.py path/to/your_file.xlsx --output full_report --ai --model qwen2.5:7b
```

Interactive invoice/quotation from terminal:

```bash
python run_cli.py path/to/your_file.xlsx --output invoice
python run_cli.py path/to/your_file.xlsx --output quotation
```

## Create a sample workbook

```bash
python sample_generator.py
```

This creates:

```text
sample_business_input.xlsx
```

You can upload it in the browser app or run:

```bash
python run_cli.py sample_business_input.xlsx --output full_report --currency "€"
```

Sample HTML files have also been generated in `generated/`.

## What the tool needs for best results

### For invoice and quotation drafting

At minimum, the workbook should contain something like:

- product/item name or description
- SKU/item code if available
- sales price or unit price
- optional cost columns for margin visibility

### For margin analysis

Best columns:

- product/item name
- unit price / sales price
- unit cost OR material + labor + handling + overhead costs
- quantity/demand/sales volume if available

### For production optimization

Best columns:

- product/item name or SKU
- production location / plant / country / factory / site
- unit cost OR cost components
- demand/production volume
- capacity by location if available
- handling/logistics/freight costs if available

### For market comparison

A local model does **not** have live market prices by itself. For reliable market comparison, include market/competitor benchmark data in the workbook, such as:

- competitor name
- similar product name
- market price
- region
- source/date if available

A future version can add connectors for web/API market data, but this MVP keeps everything local.

## Limitations of this MVP

- Arbitrary Excel reading is heuristic. It can infer many messy workbooks, but not all.
- Merged cells, multi-level headers and heavily formatted reports may need cleanup.
- AI text is advisory. Financial, tax, legal and production decisions should be validated by a human.
- Market comparison is only as current as the uploaded workbook data unless you add an external data connector.
- Invoice and quotation HTML is a draft template, not jurisdiction-specific legal/tax documentation.

## Recommended next improvements

1. Add a manual column-mapping screen so users can correct detected roles.
2. Add a saved configuration per supplier/customer workbook type.
3. Add PDF export.
4. Add an optional live market-data connector.
5. Add stronger optimization constraints: minimum order quantities, tariffs, lead time, CO₂, risk diversification and supplier reliability.
6. Add authentication if used by multiple people on a network.
