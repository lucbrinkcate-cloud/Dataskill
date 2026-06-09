# Feature Roadmap for the Business Process Excel Agent Skill

## Implemented in this workspace

- Hermes/Agent-Skills compatible `SKILL.md` package.
- Wrapper script that lets an agent call the Python engine from Hermes, Claude-style skills, Codex-style skills, or a custom harness.
- Batch processing for files, directories, and globs.
- Natural-language request mapping to output types.
- Deterministic HTML generation for:
  - invoices
  - quotations
  - full reports
  - margin analysis
  - production optimization
  - product/component/market comparison
  - schema/readiness reports
- Editable HTML/Jinja2 invoice and quotation templates.
- Template commands: list, create, show, update, delete, context preview.
- Optional local AI narrative commentary through Ollama-compatible local models.

## Recommended next high-value features

### 1. Manual column-mapping profiles

For recurring messy supplier/customer files, let the user save a mapping like:

```yaml
profile: supplier_a_price_list
sheet: Products
columns:
  sku: Article No.
  product: Description EN
  unit_price: Net Sales Price
  material_cost: Material EUR
  location: Plant
```

Then agents can run:

```bash
business_excel_skill.py batch --files supplier_a/*.xlsx --mapping supplier_a_price_list --output margin_analysis
```

### 2. Template variables UI/report

Create an HTML page that shows all available template variables and sample values so business users can edit invoice templates without reading JSON.

### 3. PDF export

Add optional HTML-to-PDF export through Playwright, WeasyPrint, wkhtmltopdf, or browser print automation.

### 4. DOCX/XLSX export

Add docx templates through `docxtpl` for companies that require Word quotation/invoice formats, and XLSX export for finance teams.

### 5. Approval workflow

Generated invoices/quotes should have states:

- draft
- internally reviewed
- approved
- sent
- rejected/revised

This can be tracked in a local SQLite database.

### 6. Accounting/ERP connectors

Optional connectors:

- Exact Online
- Moneybird
- QuickBooks
- Xero
- SAP/Business Central exports
- generic webhook/API

### 7. Market-data connectors

The local LLM should not invent market prices. Add explicit connectors for:

- uploaded competitor files
- supplier APIs
- web search/browser extraction with source citations
- approved product catalogs

### 8. Advanced production optimization

Add constraints beyond lowest unit cost:

- minimum order quantities
- plant capacity by period
- shipping/tariff/customs
- lead time
- safety stock
- supplier risk
- CO2/ESG score
- currency fluctuation
- dual-source requirements

### 9. Scenario/sensitivity analysis

Generate reports such as:

- raw material price +10% / -10%
- labor cost by location changes
- logistics cost shock
- exchange-rate sensitivity
- price increase needed to maintain target margin

### 10. RAG knowledge base

Let the skill use a local folder of company policies, pricing rules, terms and conditions, customer-specific discounts, and production constraints.

### 11. Validation and audit trails

Each generated output should include machine-readable provenance:

- input files and hashes
- columns used
- assumptions
- model used, if AI commentary was enabled
- timestamp
- template version

### 12. MCP server adapter

Expose the same functions as Model Context Protocol tools for harnesses that prefer MCP instead of shell-based skills.

### 13. Security hardening

- Run in a restricted working directory.
- Never execute macros from uploaded Excel files.
- Add size/row limits.
- Add PII redaction option before local LLM commentary.
- Add prompt-injection warnings for workbook text fields.

### 14. Multi-company template packs

Support template packs:

```text
template_packs/
  acme_bv/
    invoice.html.j2
    quotation.html.j2
    terms.html
    logo.svg
    settings.yaml
```

### 15. Human-in-the-loop clarification mode

When the tool is unsure, it should output a compact question set for the agent/user:

- Which sheet contains products?
- Which column is sales price?
- Should tax be 0%, 9%, 21%, or custom?
- Which products should be included in the invoice?

