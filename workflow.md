# Mandatory Agent Workflow

Use this when operating the Business Process Excel Analyst skill from Hermes or another agent harness.

## Principle

The dashboard is pre-built. The assigned agent should not rebuild it on every run. The agent should use the dashboard or CLI to orchestrate the workflow.

## Interactive browser workflow

1. Launch local dashboard:

```bash
cd /path/to/local_business_ai
python app.py
```

2. Open `http://127.0.0.1:5000`.
3. First run: complete setup wizard. If the user leaves fields blank, placeholders are used.
4. Upload Excel/CSV files.
5. Toggle outputs and formats.
6. Create plan.
7. User reviews detection and confirms or changes approach.
8. Generate outputs only after confirmation.
9. Review approval register.

## Agent CLI workflow

1. Inspect:

```bash
python scripts/business_excel_skill.py inspect --files "data/*.xlsx"
```

2. Summarize detection to user:

- files found
- sheets detected
- inferred columns
- product rows
- possible outputs
- warnings/assumptions

3. Ask for confirmation:

```text
I plan to generate: full_report, margin_analysis, production_optimization in HTML/PDF/DOCX. Confirm, or tell me what to change?
```

4. After confirmation:

```bash
python scripts/business_excel_skill.py batch --files "data/*.xlsx" --output full_report,margin_analysis,production_optimization --formats html,pdf,docx --audit
```

5. Return file paths.

## Never do this

- Do not generate invoices/reports before the user confirms the plan.
- Do not let the LLM do spreadsheet arithmetic manually when the CLI can do it.
- Do not invent market prices. Use uploaded market files, approved web research, or configured connectors.
- Do not mark outputs as approved automatically.

