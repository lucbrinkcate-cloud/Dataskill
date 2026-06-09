#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[1/3] Installing Python requirements..."
"$PYTHON_BIN" -m pip install --user -r requirements.txt

echo "[2/3] Installing Hermes skill..."
"$PYTHON_BIN" install_agent_skill.py --target hermes --force

echo "[3/3] Verifying skill wrapper..."
"$PYTHON_BIN" "$HOME/.hermes/skills/business-process-excel-analyst/scripts/business_excel_skill.py" templates list --compact >/dev/null

echo ""
echo "Business Process Excel Analyst installed."
echo "Dashboard command:"
echo "  cd $(pwd) && $PYTHON_BIN app.py"
echo "Then open: http://127.0.0.1:5000"
echo ""
echo "Hermes skill path: $HOME/.hermes/skills/business-process-excel-analyst"
