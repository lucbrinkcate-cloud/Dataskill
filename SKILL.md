---
name: business-process-excel-analyst
description: Use this skill when the user wants to process one or more Excel/CSV files into invoices, quotations, margin reports, production-location/volume optimization, product/component/market comparisons, or workbook schema reports. It wraps a local CLI and supports editable saved HTML/Jinja templates.
version: 1.0.0
author: Arena.ai generated for local use
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [business, excel, invoices, quotations, manufacturing, margin-analysis, production-optimization, local-ai]
    category: productivity
    config:
      - key: business_ai.home
        description: Path to the local_business_ai engine directory containing skill_cli.py and core/
        default: BUSINESS_AI_HOME environment variable or engine_path.txt in this skill folder
        prompt: Set BUSINESS_AI_HOME or run install_agent_skill.py from the project
---

# Business Process Excel Analyst

## When to Use
Use this skill when the user gives Excel/CSV files and asks for any of these outputs:
- invoice draft or quote/quotation draft
- full HTML business report
- margin/profit analysis
- production cost/location/capacity/volume split recommendation
- product/component comparison, including competitor or market benchmark data from workbook sheets
- schema/readiness report for messy workbooks
- creating, saving, editing, listing, or reusing invoice/quotation HTML templates
- batch processing a list, folder, or glob of Excel files

## Core Rule
Do not manually inspect and summarize spreadsheets when the local CLI can do it. Use `scripts/business_excel_skill.py` so calculations, schema inference, and HTML generation are deterministic and repeatable.

## Quick Reference
From this skill directory, run:

```bash
python scripts/business_excel_skill.py inspect --files "path/to/*.xlsx"
python scripts/business_excel_skill.py batch --files "path/to/*.xlsx" --request "make a full report and margin analysis" --out-dir outputs
python scripts/business_excel_skill.py document --file workbook.xlsx --type invoice --select sku:A-100,B-200 --quantities 'A-100:10,B-200:5' --company "Seller" --customer "Buyer" --out outputs/invoice.html
python scripts/business_excel_skill.py templates list
python scripts/business_excel_skill.py templates create --name my_invoice --from-template invoice_basic
python scripts/business_excel_skill.py templates show --name my_invoice
python scripts/business_excel_skill.py templates context --file workbook.xlsx --type invoice --select all --out template_context.json
```

If the wrapper cannot find the engine, set:

```bash
export BUSINESS_AI_HOME=/absolute/path/to/local_business_ai
```

## Procedure
1. Identify the input files.
   - Accept direct paths, folders, or glob patterns such as `data/*.xlsx`.
   - If the user says "these files" but no paths are available, ask for the file list.
2. Inspect first unless the user explicitly gives a final command.
   - Run `inspect` to discover sheets, inferred columns, and product rows.
   - Use the JSON result to decide if invoice/quotation/margin/production outputs are possible.
3. Choose outputs.
   - Prefer explicit `--output` for deterministic runs.
   - If the user gives natural language, use `batch --request "..."`; the CLI maps keywords to outputs.
4. Generate reports.
   - Use `batch` for multiple files and one or more outputs.
   - Use `document` for a specific invoice/quotation when item selection matters.
5. For templates:
   - Use `templates list` before choosing a template.
   - Use `templates create` to make a user-editable copy.
   - Use `templates context` to see available variables before editing.
   - Use `templates update` to save a modified template file into the user template store.
6. Return absolute output paths to the user.
   - For Hermes chat gateways, include `[[as_document]]` if you want generated HTML delivered as files.

## Output Types
Use these exact output names with `--output`:
- `invoice`
- `quotation`
- `full_report`
- `margin_analysis`
- `production_optimization`
- `product_comparison`
- `schema_report`

Multiple outputs are comma-separated:

```bash
python scripts/business_excel_skill.py batch --files data/*.xlsx --output full_report,margin_analysis,production_optimization --out-dir outputs
```

## Invoice and Quotation Selection
For documents, select products using one of:
- `--select all`
- `--select top-margin`
- `--select positive-margin`
- `--select ids:0,1,2`
- `--select sku:A-100,B-200`
- `--select A-100,B-200` for comma-separated IDs/SKUs/names

Quantities can be JSON or compact syntax:

```bash
--quantities '{"A-100": 10, "B-200": 5}'
--quantities 'A-100:10,B-200:5'
```

## Local AI Use
The CLI can add local AI narrative commentary through Ollama:

```bash
python scripts/business_excel_skill.py batch --files data/*.xlsx --output full_report --ai --model qwen2.5:7b --ollama-url http://localhost:11434
```

Only use AI for narrative explanation. Do not rely on the model for arithmetic, tax rules, or live market prices. The deterministic Python engine performs calculations.

## Pitfalls
- Arbitrary Excel files may have unclear headers. If detection is weak, generate `schema_report` and ask the user which columns map to product, price, cost, quantity, and location.
- A local LLM does not have live market prices. Use `product_comparison` only from workbook-provided market/competitor data unless another trusted market-data connector is available.
- Invoice/quotation outputs are drafts. Tell the user to validate VAT/tax/legal requirements before sending.
- Very large product lists can create huge invoice/quotation files. Use `--select` and `--max-lines`.

## Verification
After each run:
1. Check the CLI JSON has `
`"ok": true`.
2. Confirm every requested output has a `path` and the file exists.
3. If any output has `"ok": false`, read the error and either run `schema_report` or ask the user for missing mapping/selection details.
4. When returning final results, list the generated paths and a short explanation of what was created.
