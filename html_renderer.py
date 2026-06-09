from __future__ import annotations

import html
import math
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


DEFAULT_STYLE = """
:root {
  --bg: #f6f8fb;
  --panel: #ffffff;
  --text: #172033;
  --muted: #667085;
  --line: #d9e2ec;
  --primary: #2557d6;
  --primary-2: #0e7c86;
  --green: #047857;
  --amber: #b45309;
  --red: #b42318;
  --blue-soft: #eaf1ff;
  --green-soft: #e9f8ef;
  --amber-soft: #fff4df;
  --red-soft: #ffefec;
  --shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
header.hero { background: linear-gradient(135deg, #102a62 0%, #2557d6 54%, #0e7c86 100%); color: white; padding: 34px 42px; }
.hero h1 { margin: 0 0 8px; font-size: 30px; letter-spacing: -0.03em; }
.hero p { margin: 4px 0; opacity: 0.92; }
main { max-width: 1220px; margin: -22px auto 48px; padding: 0 22px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow); padding: 22px; margin: 20px 0; }
.card h2 { margin: 0 0 14px; font-size: 21px; letter-spacing: -0.02em; }
.card h3 { margin: 18px 0 10px; font-size: 16px; }
.grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }
.kpi { grid-column: span 3; background: linear-gradient(180deg, #fff, #f8fbff); border: 1px solid var(--line); border-radius: 16px; padding: 16px; }
.kpi .label { color: var(--muted); font-size: 13px; }
.kpi .value { font-size: 24px; font-weight: 800; margin-top: 6px; letter-spacing: -0.03em; }
.kpi .hint { font-size: 12px; color: var(--muted); margin-top: 7px; }
.badge { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 700; }
.badge.green { color: var(--green); background: var(--green-soft); }
.badge.amber { color: var(--amber); background: var(--amber-soft); }
.badge.red { color: var(--red); background: var(--red-soft); }
.badge.blue { color: var(--primary); background: var(--blue-soft); }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; }
th, td { padding: 10px 12px; border-bottom: 1px solid #e6edf5; text-align: left; vertical-align: top; }
th { background: #f7f9fc; color: #344054; position: sticky; top: 0; z-index: 1; }
tr:last-child td { border-bottom: 0; }
.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.small { font-size: 12px; color: var(--muted); }
.note { border-left: 4px solid var(--primary); background: #f2f6ff; padding: 12px 14px; border-radius: 12px; color: #22345c; }
.warn { border-left: 4px solid var(--amber); background: #fff8eb; padding: 12px 14px; border-radius: 12px; color: #52320a; }
.ai-box { white-space: pre-wrap; line-height: 1.55; background: #101828; color: #f9fafb; border-radius: 16px; padding: 18px; }
.footer { text-align: center; color: var(--muted); font-size: 12px; margin: 30px 0; }
.chart { width: 100%; overflow-x: auto; }
hr { border: 0; border-top: 1px solid var(--line); margin: 20px 0; }
.doc-header { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; }
.doc-title { font-size: 34px; font-weight: 900; letter-spacing: -0.04em; color: #102a62; }
.total-box { background: #102a62; color: white; padding: 16px 18px; border-radius: 16px; min-width: 260px; }
.total-box .big { font-size: 28px; font-weight: 900; margin-top: 4px; }
@media (max-width: 850px) { .kpi { grid-column: span 6; } .doc-header { flex-direction: column; } }
@media (max-width: 560px) { header.hero { padding: 26px 20px; } main { padding: 0 12px; } .kpi { grid-column: span 12; } }
@media print { body { background: white; } header.hero { background: white; color: #111; padding: 0 0 16px; } main { margin: 0; max-width: none; padding: 0; } .card { box-shadow: none; border: 1px solid #ddd; page-break-inside: avoid; } }
"""


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def fmt_number(value: Any, decimals: int = 2) -> str:
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return "—"
        if decimals == 0:
            return f"{v:,.0f}"
        return f"{v:,.{decimals}f}"
    except Exception:
        return "—"


def fmt_currency(value: Any, currency: str = "€") -> str:
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return "—"
        return f"{currency}{v:,.2f}"
    except Exception:
        return "—"


def fmt_pct(value: Any) -> str:
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return "—"
        if abs(v) <= 1.5:
            v *= 100
        return f"{v:,.1f}%"
    except Exception:
        return "—"


def kpi(label: str, value: str, hint: str = "") -> str:
    return f"<div class='kpi'><div class='label'>{esc(label)}</div><div class='value'>{esc(value)}</div><div class='hint'>{esc(hint)}</div></div>"


def badge(text: str, kind: str = "blue") -> str:
    kind = kind if kind in {"blue", "green", "amber", "red"} else "blue"
    return f"<span class='badge {kind}'>{esc(text)}</span>"


def dataframe_table(df: pd.DataFrame, currency: str = "€", max_rows: int = 100, numeric_currency_cols: Optional[Sequence[str]] = None, pct_cols: Optional[Sequence[str]] = None) -> str:
    if df is None or df.empty:
        return "<p class='small'>No data available.</p>"
    numeric_currency_cols = set(numeric_currency_cols or [])
    pct_cols = set(pct_cols or [])
    clipped = df.head(max_rows).copy()
    rows = []
    header = "".join(f"<th>{esc(c)}</th>" for c in clipped.columns)
    for _, row in clipped.iterrows():
        cells = []
        for col in clipped.columns:
            value = row[col]
            class_name = ""
            if col in numeric_currency_cols:
                display = fmt_currency(value, currency)
                class_name = " class='num'"
            elif col in pct_cols:
                display = fmt_pct(value)
                class_name = " class='num'"
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                display = fmt_number(value)
                class_name = " class='num'"
            else:
                display = esc(value)
            cells.append(f"<td{class_name}>{display}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    more = "" if len(df) <= max_rows else f"<p class='small'>Showing {max_rows} of {len(df)} rows.</p>"
    return f"<div class='table-wrap'><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>{more}"


def bar_chart(data: Sequence[Tuple[str, float]], title: str = "", currency: str = "€", max_bars: int = 10, value_type: str = "number") -> str:
    clean: List[Tuple[str, float]] = []
    for label, value in data:
        try:
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                continue
            clean.append((str(label), v))
        except Exception:
            continue
    if not clean:
        return "<p class='small'>No chart data available.</p>"
    clean = clean[:max_bars]
    max_abs = max(abs(v) for _, v in clean) or 1.0
    width = 860
    row_h = 34
    left = 205
    right = 120
    height = 38 + row_h * len(clean)
    bars = []
    for i, (label, v) in enumerate(clean):
        y = 30 + i * row_h
        bar_w = max(2, int((abs(v) / max_abs) * (width - left - right)))
        color = "#047857" if v >= 0 else "#b42318"
        if value_type == "pct":
            val_text = fmt_pct(v)
        elif value_type == "currency":
            val_text = fmt_currency(v, currency)
        else:
            val_text = fmt_number(v)
        bars.append(f"<text x='8' y='{y+18}' font-size='12' fill='#344054'>{esc(label[:34])}</text>")
        bars.append(f"<rect x='{left}' y='{y+5}' width='{bar_w}' height='18' rx='5' fill='{color}' opacity='0.88'></rect>")
        bars.append(f"<text x='{left + bar_w + 8}' y='{y+19}' font-size='12' fill='#344054'>{esc(val_text)}</text>")
    title_svg = f"<text x='8' y='18' font-size='14' font-weight='700' fill='#172033'>{esc(title)}</text>" if title else ""
    svg = f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' role='img' aria-label='{esc(title)}'>{title_svg}{''.join(bars)}</svg>"
    return f"<div class='chart'>{svg}</div>"


def render_page(title: str, subtitle: str, sections: Sequence[str], output_path: Optional[str] = None) -> str:
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{DEFAULT_STYLE}</style>
</head>
<body>
<header class="hero">
  <h1>{esc(title)}</h1>
  <p>{esc(subtitle)}</p>
  <p class="small" style="color: rgba(255,255,255,.82)">Generated {date.today().isoformat()} · Local Business AI Tool</p>
</header>
<main>
{''.join(sections)}
<div class="footer">This output is generated from uploaded workbook data. Validate financial, tax, legal, and market assumptions before business use.</div>
</main>
</body>
</html>"""
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html_doc, encoding="utf-8")
    return html_doc


def card(title: str, body: str) -> str:
    return f"<section class='card'><h2>{esc(title)}</h2>{body}</section>"
