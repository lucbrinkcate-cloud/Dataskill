# Design notes from comparable agent skill/tool ecosystems

- Hermes skills are suitable when a capability can be expressed as instructions plus shell commands or an external CLI. This skill therefore wraps a deterministic Python CLI rather than asking the LLM to do spreadsheet math directly.
- Hermes skills live under `~/.hermes/skills/`, use `SKILL.md` frontmatter, can include `scripts/` and `references/`, and follow progressive disclosure.
- Claude Code and other modern agent harnesses also use `SKILL.md` with optional script folders, making this skill portable with minimal changes.
- Existing document automation patterns commonly use Python, pandas/OpenPyXL for data extraction, and Jinja/docx-style templating for repeatable invoices/reports. This project uses HTML/Jinja templates because the requested output is HTML and because HTML is easy for agents to edit, diff, save, and render.

See the project README for setup and limitations.
