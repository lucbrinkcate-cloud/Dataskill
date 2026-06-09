# GitHub Setup and Hermes Installation

## Recommended repository layout

Push the whole `local_business_ai/` directory. The Hermes skill depends on the Python engine files, not just `SKILL.md`.

Required files/folders:

```text
app.py
skill_cli.py
install_agent_skill.py
setup_hermes.sh
requirements.txt
core/
templates/
agent_skill/business-process-excel-analyst/
```

## Fresh machine setup

```bash
git clone https://github.com/YOURNAME/YOURREPO.git
cd YOURREPO/local_business_ai
./setup_hermes.sh
```

Then start the local dashboard:

```bash
python3 app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Hermes usage prompt

```text
Use the business-process-excel-analyst skill. Work offline by default. Inspect the Excel files first, summarize what you detect, propose a plan, and wait for my confirmation before generating outputs. Save every run in its dated session folder.
```

## CLI examples

Inspect:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py inspect --files "data/*.xlsx"
```

Goal insight mining:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py batch \
  --files "data/*.xlsx" \
  --output goal_analysis,margin_analysis,production_optimization,product_comparison \
  --goal "Keep finding connections between competitor prices, our margins, production locations and cost drivers" \
  --formats html,pdf,docx \
  --offline \
  --audit \
  --out-dir outputs
```

Review insights:

```bash
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py insights list --session-dir outputs/YYYY-MM-DD/SESSION_FOLDER
python ~/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py insights set-status --session-dir outputs/YYYY-MM-DD/SESSION_FOLDER --id INSIGHT_ID --status accepted --notes "Validated by team"
```
