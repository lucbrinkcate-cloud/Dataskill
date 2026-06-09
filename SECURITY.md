# Security Notes

This project is designed for local/offline business-data processing.

## Offline mode

Use `--offline` in CLI runs or enable offline/data-security mode in the dashboard. In offline mode:

- No supplier APIs are called.
- No web market lookup is performed.
- Uploaded market/competitor files are the only market-data source.
- Localhost Ollama (`localhost`, `127.0.0.1`, `[::1]`) is allowed.
- Non-local model URLs are blocked by the skill CLI.

## Excel macro safety

The tool reads workbook cell values with Python libraries. It does not execute Excel macros.

## Sensitive data

Do not commit real uploaded workbooks, generated client outputs, credentials or `.env` files. The `.gitignore` excludes common local output and secret paths.

## Human validation

Generated invoices, quotations, pricing recommendations, production recommendations and market insights are drafts. Validate tax, legal, commercial and operational assumptions before external use.
