# Business Process Excel Analyst CLI API

This reference is for agents/harnesses that prefer a deterministic command interface.

## Inspect

```bash
python scripts/business_excel_skill.py inspect --files FILE_OR_GLOB [FILE_OR_GLOB ...]
```

Returns JSON:

```json
{
  "ok": true,
  "files": [
    {
      "path": "/abs/file.xlsx",
      "filename": "file.xlsx",
      "errors": [],
      "tables": [
        {"sheet": "Sales", "rows": 100, "columns": ["SKU"], "roles": {"sku": "SKU"}, "score": 3.2}
      ],
      "detected_product_rows": 100,
      "sample_products": []
    }
  ]
}
```

## Batch generation

```bash
python scripts/business_excel_skill.py batch \
  --files "data/*.xlsx" \
  --output full_report,margin_analysis,production_optimization \
  --out-dir outputs \
  --currency "€"
```

Natural language output inference:

```bash
python scripts/business_excel_skill.py batch --files "data/*.xlsx" --request "make margin reports and production location recommendations"
```

Output names:

- `invoice`
- `quotation`
- `full_report`
- `margin_analysis`
- `production_optimization`
- `product_comparison`
- `schema_report`

## Single invoice/quotation

```bash
python scripts/business_excel_skill.py document \
  --file workbook.xlsx \
  --type invoice \
  --select sku:A-100,B-200 \
  --quantities 'A-100:10,B-200:5' \
  --company "Seller BV" \
  --customer "Buyer BV" \
  --tax-rate 21 \
  --template invoice_basic \
  --out outputs/invoice.html
```

## Template management

List templates:

```bash
python scripts/business_excel_skill.py templates list
```

Create editable copy:

```bash
python scripts/business_excel_skill.py templates create --name acme_invoice --from-template invoice_basic
```

Show template source:

```bash
python scripts/business_excel_skill.py templates show --name acme_invoice
```

Generate context JSON for template editing:

```bash
python scripts/business_excel_skill.py templates context --file workbook.xlsx --type invoice --select all --out context.json
```

Update/save template from edited file:

```bash
python scripts/business_excel_skill.py templates update --name acme_invoice --file edited_invoice.html.j2
```

Use saved template:

```bash
python scripts/business_excel_skill.py document --file workbook.xlsx --type invoice --template acme_invoice --select all
```

## Template variables

Templates are HTML/Jinja2. Main variables:

- `style`: default CSS
- `generated_date`
- `workbook.filename`, `workbook.path`
- `document.type`, `document.number`, `document.date`, `document.valid_until`
- `document.currency`, `document.tax_rate`, `document.subtotal`, `document.tax`, `document.total`, `document.notes`
- `company.name`
- `customer.name`
- `lines`: list of selected line items
  - `line.index`
  - `line.sku`
  - `line.description`
  - `line.category`
  - `line.location`
  - `line.quantity`
  - `line.unit_price`
  - `line.line_total`
  - `line.unit_cost`
  - `line.margin_unit`
  - `line.margin_pct`

Filters:

- `{{ value|currency(document.currency) }}`
- `{{ value|number(2) }}`
- `{{ value|pct }}`

## Exit codes

- `0`: success
- `1`: generation error or partial failure
- `2`: bad input/no files
- `130`: interrupted
