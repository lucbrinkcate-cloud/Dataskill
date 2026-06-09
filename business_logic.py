from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from .excel_reader import SheetTable, WorkbookData
from .html_renderer import badge, bar_chart, card, dataframe_table, esc, fmt_currency, fmt_number, fmt_pct, kpi, render_page
from .llm import OllamaClient
from .schema_mapper import COST_ROLES, first_existing, normalize_text, safe_number


@dataclass
class ProductItem:
    id: str
    source_sheet: str
    source_row: int
    sku: str = ""
    name: str = ""
    category: str = ""
    location: str = ""
    supplier: str = ""
    unit_price: float = math.nan
    unit_cost: float = math.nan
    material_cost: float = math.nan
    labor_cost: float = math.nan
    handling_cost: float = math.nan
    overhead_cost: float = math.nan
    quantity: float = math.nan
    capacity: float = math.nan
    margin_pct: float = math.nan
    raw: Dict[str, Any] = field(default_factory=dict)

    def total_cost(self) -> float:
        # Prefer explicit unit cost, otherwise sum components.
        if self.unit_cost == self.unit_cost and self.unit_cost > 0:
            return float(self.unit_cost)
        total = 0.0
        found = False
        for v in [self.material_cost, self.labor_cost, self.handling_cost, self.overhead_cost]:
            if v == v:
                total += float(v)
                found = True
        return total if found else float("nan")

    def margin_value(self) -> float:
        c = self.total_cost()
        if self.unit_price == self.unit_price and c == c:
            return self.unit_price - c
        return float("nan")

    def margin_rate(self) -> float:
        if self.margin_pct == self.margin_pct:
            return self.margin_pct / 100.0 if abs(self.margin_pct) > 1.5 else self.margin_pct
        mv = self.margin_value()
        if self.unit_price == self.unit_price and self.unit_price:
            return mv / self.unit_price
        return float("nan")

    def display_name(self) -> str:
        if self.name and self.sku:
            return f"{self.sku} — {self.name}"
        return self.name or self.sku or f"Row {self.source_row + 1}"


@dataclass
class SelectedLine:
    product: ProductItem
    quantity: float
    override_price: Optional[float] = None
    discount_pct: float = 0.0

    @property
    def unit_price(self) -> float:
        if self.override_price is not None and self.override_price == self.override_price:
            return self.override_price
        if self.product.unit_price == self.product.unit_price:
            return self.product.unit_price
        # Fallback: cost plus 30% markup if no sales price exists.
        c = self.product.total_cost()
        return c * 1.30 if c == c else 0.0

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price * (1 - self.discount_pct / 100.0)


def _get_cell(row: pd.Series, col: Optional[str], default: Any = "") -> Any:
    if not col or col not in row:
        return default
    value = row[col]
    if pd.isna(value):
        return default
    return value


def _get_num(row: pd.Series, col: Optional[str], default: float = math.nan) -> float:
    if not col or col not in row:
        return default
    return safe_number(row[col], default)


def extract_products(workbook: WorkbookData, max_rows_per_table: int = 5000) -> List[ProductItem]:
    products: List[ProductItem] = []
    for table in workbook.tables:
        schema = table.schema
        if not schema:
            continue
        roles = schema.roles
        # A table can be product-like if it has a name/code plus either price/cost/quantity/location.
        has_identity = any(r in roles for r in ["product", "sku"])
        has_business_values = any(r in roles for r in ["unit_price", "unit_cost", "material_cost", "labor_cost", "handling_cost", "overhead_cost", "quantity", "location", "capacity", "margin"])
        # Competitor/market benchmark sheets often contain product names and market prices,
        # but they are not company products to invoice or manufacture. Keep them for the
        # market-comparison section instead of mixing them into internal product rows.
        looks_like_external_market = "competitor" in roles and not any(
            r in roles for r in ["unit_cost", "material_cost", "labor_cost", "handling_cost", "overhead_cost", "quantity", "capacity"]
        )
        if not (has_identity and has_business_values) or looks_like_external_market:
            continue
        product_col = schema.role_column("product")
        sku_col = schema.role_column("sku")
        category_col = schema.role_column("category")
        location_col = schema.role_column("location")
        supplier_col = schema.role_column("supplier")
        price_col = schema.role_column("unit_price")
        cost_col = schema.role_column("unit_cost")
        material_col = schema.role_column("material_cost")
        labor_col = schema.role_column("labor_cost")
        handling_col = schema.role_column("handling_cost")
        overhead_col = schema.role_column("overhead_cost")
        qty_col = schema.role_column("quantity")
        capacity_col = schema.role_column("capacity")
        margin_col = schema.role_column("margin")
        for idx, row in table.dataframe.head(max_rows_per_table).iterrows():
            name = str(_get_cell(row, product_col, "")).strip()
            sku = str(_get_cell(row, sku_col, "")).strip()
            if not name and not sku:
                continue
            item = ProductItem(
                id=f"{len(products)}",
                source_sheet=table.name,
                source_row=int(idx),
                sku=sku,
                name=name,
                category=str(_get_cell(row, category_col, "")).strip(),
                location=str(_get_cell(row, location_col, "")).strip(),
                supplier=str(_get_cell(row, supplier_col, "")).strip(),
                unit_price=_get_num(row, price_col),
                unit_cost=_get_num(row, cost_col),
                material_cost=_get_num(row, material_col),
                labor_cost=_get_num(row, labor_col),
                handling_cost=_get_num(row, handling_col),
                overhead_cost=_get_num(row, overhead_col),
                quantity=_get_num(row, qty_col),
                capacity=_get_num(row, capacity_col),
                margin_pct=_get_num(row, margin_col),
                raw=row.where(pd.notna(row), "").to_dict(),
            )
            # Filter obvious metadata rows.
            if normalize_text(item.name) in {"total", "subtotal", "grand total"}:
                continue
            products.append(item)
    return products


def products_to_dataframe(products: Sequence[ProductItem]) -> pd.DataFrame:
    rows = []
    for p in products:
        rows.append({
            "ID": p.id,
            "Sheet": p.source_sheet,
            "SKU": p.sku,
            "Product": p.name,
            "Category": p.category,
            "Location": p.location,
            "Supplier": p.supplier,
            "Unit price": p.unit_price,
            "Total unit cost": p.total_cost(),
            "Material": p.material_cost,
            "Labor": p.labor_cost,
            "Handling": p.handling_cost,
            "Overhead": p.overhead_cost,
            "Margin/unit": p.margin_value(),
            "Margin %": p.margin_rate(),
            "Quantity/demand": p.quantity,
            "Capacity": p.capacity,
        })
    return pd.DataFrame(rows)


def product_options_html(products: Sequence[ProductItem], currency: str = "€", max_rows: int = 300) -> str:
    if not products:
        return "<p class='warn'>No product-like rows were detected. Upload a workbook containing product/item names plus price or cost columns.</p>"
    rows = []
    for p in products[:max_rows]:
        price = fmt_currency(p.unit_price if p.unit_price == p.unit_price else p.total_cost() * 1.3, currency)
        cost = fmt_currency(p.total_cost(), currency)
        margin = fmt_pct(p.margin_rate())
        rows.append(f"""
        <tr>
          <td><input type="checkbox" name="selected" value="{esc(p.id)}"></td>
          <td><strong>{esc(p.display_name())}</strong><div class="small">Sheet: {esc(p.source_sheet)} · Location: {esc(p.location or '—')}</div></td>
          <td>{esc(p.category or '—')}</td>
          <td class="num">{price}</td>
          <td class="num">{cost}</td>
          <td class="num">{margin}</td>
          <td><input type="number" name="qty_{esc(p.id)}" min="0" step="0.01" placeholder="0" style="width:90px"></td>
          <td><input type="number" name="price_{esc(p.id)}" min="0" step="0.01" placeholder="optional" style="width:105px"></td>
        </tr>
        """)
    more = "" if len(products) <= max_rows else f"<p class='small'>Showing first {max_rows} detected products. Refine the workbook or use CLI for very large documents.</p>"
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr><th>Select</th><th>Item</th><th>Category</th><th>Detected price</th><th>Detected cost</th><th>Margin</th><th>Quantity</th><th>Override unit price</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>{more}
    """


def _selected_lines_from_form(products: Sequence[ProductItem], form: Dict[str, Any]) -> List[SelectedLine]:
    selected = form.getlist("selected") if hasattr(form, "getlist") else form.get("selected", [])
    if isinstance(selected, str):
        selected = [selected]
    by_id = {p.id: p for p in products}
    lines: List[SelectedLine] = []
    for pid in selected:
        p = by_id.get(str(pid))
        if not p:
            continue
        qty = safe_number(form.get(f"qty_{pid}", 0), 0.0)
        if qty <= 0:
            qty = 1.0
        price_raw = form.get(f"price_{pid}", "")
        override_price = None
        if str(price_raw).strip():
            override_price = safe_number(price_raw, math.nan)
        lines.append(SelectedLine(product=p, quantity=qty, override_price=override_price))
    return lines


def render_invoice_or_quote(
    document_type: str,
    lines: Sequence[SelectedLine],
    company: str = "Your Company",
    customer: str = "Customer",
    currency: str = "€",
    tax_rate: float = 21.0,
    notes: str = "",
    output_path: Optional[str] = None,
    llm_summary: str = "",
) -> str:
    document_type = "Quotation" if document_type.lower().startswith("quote") else "Invoice"
    doc_no_prefix = "QUO" if document_type == "Quotation" else "INV"
    doc_no = f"{doc_no_prefix}-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    subtotal = sum(line.line_total for line in lines)
    tax = subtotal * (tax_rate / 100.0)
    total = subtotal + tax
    valid_until = date.today() + timedelta(days=30)

    line_rows = []
    for line in lines:
        p = line.product
        cost = p.total_cost()
        margin = line.unit_price - cost if cost == cost else math.nan
        line_rows.append({
            "SKU": p.sku,
            "Description": p.name or p.display_name(),
            "Location": p.location,
            "Qty": line.quantity,
            "Unit price": line.unit_price,
            "Discount %": line.discount_pct,
            "Line total": line.line_total,
            "Est. margin/unit": margin,
            "Margin %": (margin / line.unit_price) if line.unit_price else math.nan,
        })
    df = pd.DataFrame(line_rows)
    body = f"""
    <div class="doc-header">
      <div>
        <div class="doc-title">{esc(document_type)}</div>
        <p><strong>{esc(company)}</strong><br>{esc(customer)}</p>
        <p class="small">Document no: {esc(doc_no)}<br>Date: {date.today().isoformat()}<br>{'Valid until: ' + valid_until.isoformat() if document_type == 'Quotation' else 'Payment due: ' + valid_until.isoformat()}</p>
      </div>
      <div class="total-box"><div>Total incl. tax</div><div class="big">{fmt_currency(total, currency)}</div><div class="small" style="color:rgba(255,255,255,.78)">Subtotal {fmt_currency(subtotal, currency)} · Tax {fmt_currency(tax, currency)}</div></div>
    </div>
    <hr>
    {dataframe_table(df, currency=currency, numeric_currency_cols=['Unit price','Line total','Est. margin/unit'], pct_cols=['Discount %','Margin %'])}
    <div style="max-width:440px;margin-left:auto;margin-top:18px" class="table-wrap">
      <table>
        <tr><th>Subtotal</th><td class="num">{fmt_currency(subtotal, currency)}</td></tr>
        <tr><th>Tax/VAT {fmt_pct(tax_rate/100)}</th><td class="num">{fmt_currency(tax, currency)}</td></tr>
        <tr><th>Total</th><td class="num"><strong>{fmt_currency(total, currency)}</strong></td></tr>
      </table>
    </div>
    {f'<div class="note"><strong>Notes:</strong><br>{esc(notes)}</div>' if notes else ''}
    {f'<h3>AI-assisted commercial note</h3><div class="ai-box">{esc(llm_summary)}</div>' if llm_summary else ''}
    """
    return render_page(document_type, f"{doc_no} · {company}", [card(document_type, body)], output_path)


def _valid_margin_products(products: Sequence[ProductItem]) -> List[ProductItem]:
    return [p for p in products if p.unit_price == p.unit_price and p.unit_price > 0 and p.total_cost() == p.total_cost()]


def margin_analysis(workbook: WorkbookData, currency: str = "€", llm: Optional[OllamaClient] = None, output_path: Optional[str] = None) -> str:
    products = extract_products(workbook)
    valid = _valid_margin_products(products)
    df = products_to_dataframe(valid)
    if not valid:
        sections = [card("Margin analysis", "<p class='warn'>No rows with both unit price and unit cost/component costs were detected. Add price and cost columns to the workbook or adjust column names.</p>")]
        return render_page("Margin Analysis", workbook.filename, sections, output_path)

    df["Estimated total profit"] = df["Margin/unit"] * df["Quantity/demand"].fillna(1)
    avg_margin = df["Margin %"].dropna().mean()
    best = df.sort_values("Margin %", ascending=False).head(10)
    worst = df.sort_values("Margin %", ascending=True).head(10)
    total_profit = df["Estimated total profit"].dropna().sum()
    revenue = (df["Unit price"] * df["Quantity/demand"].fillna(1)).dropna().sum()
    cogs = (df["Total unit cost"] * df["Quantity/demand"].fillna(1)).dropna().sum()

    kpis = "<div class='grid'>" + "".join([
        kpi("Detected products", fmt_number(len(valid), 0), "Rows with price and cost"),
        kpi("Average margin", fmt_pct(avg_margin), "Unweighted average margin"),
        kpi("Estimated profit", fmt_currency(total_profit, currency), "Uses quantity/demand when detected"),
        kpi("Revenue / COGS", f"{fmt_currency(revenue, currency)} / {fmt_currency(cogs, currency)}", "Workbook-derived"),
    ]) + "</div>"

    suggestion_rows = []
    for _, row in worst.head(8).iterrows():
        reasons = []
        if row.get("Handling", math.nan) == row.get("Handling", math.nan) and row["Total unit cost"]:
            handling_share = row["Handling"] / row["Total unit cost"]
            if handling_share > 0.18:
                reasons.append("handling/logistics is a high cost share")
        if row["Margin %"] < avg_margin:
            gap = avg_margin - row["Margin %"]
            reasons.append(f"margin is {fmt_pct(gap)} below average")
        if row["Unit price"] and row["Margin %"] < 0.15:
            target_price = row["Total unit cost"] / max(0.01, 1 - max(avg_margin, 0.20))
            reasons.append(f"target price near {fmt_currency(target_price, currency)} to reach healthier margin")
        suggestion_rows.append({
            "Product": row["Product"] or row["SKU"],
            "Current margin": row["Margin %"],
            "Main improvement angle": "; ".join(reasons) or "review price, BOM, supplier terms, and production location",
        })
    suggestions = pd.DataFrame(suggestion_rows)

    ai_text = ""
    if llm:
        prompt = f"""
You are a manufacturing and commercial finance analyst. Explain the margin performance from this workbook in practical business language.
Focus on strongest margins, weakest margins, likely reasons, and concrete improvement actions. Do not invent exact market prices.

Workbook file: {workbook.filename}
Average margin: {avg_margin}
Top products: {best[['SKU','Product','Category','Location','Unit price','Total unit cost','Margin %','Quantity/demand']].to_dict(orient='records')}
Weak products: {worst[['SKU','Product','Category','Location','Unit price','Total unit cost','Margin %','Quantity/demand']].to_dict(orient='records')}
"""
        result = llm.generate(prompt, system="Return concise executive insight with bullet points. Use only the provided workbook data for numeric claims.")
        ai_text = result.text if result.ok else f"Local AI insight unavailable: {result.error}"

    chart_data = [(str(r["Product"] or r["SKU"]), float(r["Margin %"])) for _, r in best.iterrows()]
    worst_chart = [(str(r["Product"] or r["SKU"]), float(r["Margin %"])) for _, r in worst.iterrows()]
    sections = [
        card("Executive KPIs", kpis),
        card("Strongest margin products", bar_chart(chart_data, "Top margin %", currency, value_type="pct") + dataframe_table(best, currency, numeric_currency_cols=["Unit price", "Total unit cost", "Margin/unit", "Estimated total profit"], pct_cols=["Margin %"])),
        card("Underperforming margins and improvement options", bar_chart(worst_chart, "Lowest margin %", currency, value_type="pct") + dataframe_table(suggestions, currency, pct_cols=["Current margin"])),
    ]
    if ai_text:
        sections.append(card("Local AI commentary", f"<div class='ai-box'>{esc(ai_text)}</div>"))
    return render_page("Margin Analysis", f"Workbook: {workbook.filename}", sections, output_path)


def production_optimization(workbook: WorkbookData, currency: str = "€", llm: Optional[OllamaClient] = None, output_path: Optional[str] = None) -> str:
    products = extract_products(workbook)
    df = products_to_dataframe(products)
    if df.empty or "Location" not in df.columns or not df["Location"].astype(str).str.strip().any():
        sections = [card("Production optimization", "<p class='warn'>No production/location column was detected. To optimize location split, include columns such as country/plant/site plus unit cost or cost components, demand, and optional capacity.</p>")]
        return render_page("Production Optimization", workbook.filename, sections, output_path)

    df = df[df["Location"].astype(str).str.strip() != ""].copy()
    df["Demand"] = df["Quantity/demand"].apply(lambda x: x if x == x and x > 0 else 1.0)
    # Aggregate by product+location, choosing lowest detected cost for duplicate rows.
    usable = df[df["Total unit cost"].notna()].copy()
    if usable.empty:
        sections = [card("Production optimization", "<p class='warn'>Locations were detected, but no unit cost or cost-component columns were found.</p>")]
        return render_page("Production Optimization", workbook.filename, sections, output_path)

    grouped_rows = []
    for (product, sku), prod_df in usable.groupby(["Product", "SKU"], dropna=False):
        demand = prod_df["Demand"].max() if prod_df["Demand"].notna().any() else 1.0
        # If product name missing, use SKU.
        product_label = product or sku or "Unnamed product"
        locs = prod_df.sort_values("Total unit cost")
        remaining = demand
        for _, loc_row in locs.iterrows():
            capacity = loc_row.get("Capacity", math.nan)
            if capacity == capacity and capacity > 0:
                qty = min(remaining, capacity)
            else:
                qty = remaining
            if qty <= 0:
                continue
            grouped_rows.append({
                "Product": product_label,
                "SKU": sku,
                "Recommended location": loc_row["Location"],
                "Allocated volume": qty,
                "Unit cost": loc_row["Total unit cost"],
                "Estimated production cost": qty * loc_row["Total unit cost"],
                "Reason": "lowest landed/unit cost" if len(locs) > 1 else "only detected location",
            })
            remaining -= qty
            if remaining <= 0:
                break
        if remaining > 0 and len(locs) > 0:
            # Capacity shortage; allocate residual to lowest cost as warning.
            loc_row = locs.iloc[0]
            grouped_rows.append({
                "Product": product_label,
                "SKU": sku,
                "Recommended location": loc_row["Location"],
                "Allocated volume": remaining,
                "Unit cost": loc_row["Total unit cost"],
                "Estimated production cost": remaining * loc_row["Total unit cost"],
                "Reason": "capacity shortage fallback; validate capacity data",
            })

    rec = pd.DataFrame(grouped_rows)
    location_summary = rec.groupby("Recommended location", as_index=False).agg({
        "Allocated volume": "sum",
        "Estimated production cost": "sum",
    }).sort_values("Estimated production cost", ascending=False)
    location_costs = usable.groupby("Location", as_index=False).agg({
        "Total unit cost": ["mean", "min", "max"],
        "Material": "mean",
        "Labor": "mean",
        "Handling": "mean",
        "Overhead": "mean",
    })
    location_costs.columns = [" ".join(c).strip() for c in location_costs.columns.to_flat_index()]
    # Raw material fluctuation proxy: range of material cost by location.
    raw_fluct = usable.groupby("Location", as_index=False).agg({"Material": ["mean", "min", "max"]})
    raw_fluct.columns = [" ".join(c).strip() for c in raw_fluct.columns.to_flat_index()]
    if "Material max" in raw_fluct and "Material min" in raw_fluct:
        raw_fluct["Material fluctuation"] = raw_fluct["Material max"] - raw_fluct["Material min"]

    ai_text = ""
    if llm:
        prompt = f"""
You are a production strategy analyst. Interpret the production location optimization below.
Explain where production should be structured, how volume should be divided, and what data risks/assumptions should be checked.
Use the workbook data only for numeric claims.

Recommended allocation: {rec.head(50).to_dict(orient='records')}
Location cost summary: {location_costs.head(50).to_dict(orient='records')}
Raw material fluctuation proxy: {raw_fluct.head(50).to_dict(orient='records')}
"""
        result = llm.generate(prompt, system="Return concise, practical recommendations with bullet points and caveats.")
        ai_text = result.text if result.ok else f"Local AI insight unavailable: {result.error}"

    total_cost = rec["Estimated production cost"].sum() if not rec.empty else 0
    total_volume = rec["Allocated volume"].sum() if not rec.empty else 0
    cheapest_location = usable.groupby("Location")["Total unit cost"].mean().sort_values().index[0]
    sections = [
        card("Production structure KPIs", "<div class='grid'>" + "".join([
            kpi("Recommended total volume", fmt_number(total_volume, 0), "Based on detected demand/quantity"),
            kpi("Estimated production cost", fmt_currency(total_cost, currency), "Recommended allocation"),
            kpi("Lowest average cost location", str(cheapest_location), "Mean detected unit cost"),
            kpi("Detected locations", fmt_number(usable["Location"].nunique(), 0), "Plants/countries/sites"),
        ]) + "</div>"),
        card("Recommended volume split", bar_chart([(str(r["Recommended location"]), float(r["Allocated volume"])) for _, r in location_summary.iterrows()], "Volume by location", currency, value_type="number") + dataframe_table(rec, currency, numeric_currency_cols=["Unit cost", "Estimated production cost"])),
        card("Production costs by location", dataframe_table(location_costs, currency, numeric_currency_cols=[c for c in location_costs.columns if c != "Location"])),
        card("Raw material price fluctuation proxy", dataframe_table(raw_fluct, currency, numeric_currency_cols=[c for c in raw_fluct.columns if c != "Location"])),
    ]
    if ai_text:
        sections.append(card("Local AI production recommendation", f"<div class='ai-box'>{esc(ai_text)}</div>"))
    return render_page("Production Optimization", f"Workbook: {workbook.filename}", sections, output_path)


def product_comparison(workbook: WorkbookData, currency: str = "€", llm: Optional[OllamaClient] = None, output_path: Optional[str] = None) -> str:
    products = extract_products(workbook)
    df = products_to_dataframe(products)
    if df.empty:
        sections = [card("Product comparison", "<p class='warn'>No product-like table was detected. Include product/item descriptions and price/cost/component columns.</p>")]
        return render_page("Product Comparison", workbook.filename, sections, output_path)

    # Group similar internal products by category when available, otherwise product token prefix.
    df["Compare group"] = df["Category"].where(df["Category"].astype(str).str.strip() != "", df["Product"].astype(str).str.lower().str.extract(r"([a-zA-Z]+)", expand=False).fillna("Ungrouped"))
    group_summary = df.groupby("Compare group", as_index=False).agg({
        "Product": "count",
        "Unit price": "mean",
        "Total unit cost": "mean",
        "Margin %": "mean",
        "Handling": "mean",
        "Material": "mean",
        "Labor": "mean",
    }).rename(columns={"Product": "Products in group"}).sort_values("Margin %", ascending=False)

    # Market/external benchmark detection.
    market_tables = []
    for table in workbook.tables:
        name = normalize_text(table.name)
        roles = table.schema.roles if table.schema else {}
        if "competitor" in roles or "market" in name or "competitor" in name or "benchmark" in name:
            market_tables.append(table)
    market_note = ""
    market_html = ""
    if market_tables:
        samples = []
        for t in market_tables[:3]:
            samples.append(t.dataframe.head(20))
        market_df = pd.concat(samples, ignore_index=True, sort=False) if samples else pd.DataFrame()
        market_html = dataframe_table(market_df, currency=currency, max_rows=50)
        market_note = badge("Market/competitor sheet detected", "green")
    else:
        market_note = badge("No explicit market price sheet detected", "amber") + " <span class='small'>For current market comparison, add competitor/market benchmark data to the workbook. A local model has no live internet prices by itself.</span>"

    ai_text = ""
    if llm:
        prompt = f"""
You are a product and component comparison analyst. Compare the company's products/components using the data below.
Focus on cost drivers, handling costs, sales margins, similar internal products, and what would be needed for market benchmarking.
If competitor/market data is missing, clearly say that live market claims are not verified.

Product group summary: {group_summary.head(50).to_dict(orient='records')}
Product sample: {df.head(60).to_dict(orient='records')}
Market tables detected: {bool(market_tables)}
"""
        result = llm.generate(prompt, system="Return concise practical insights. Do not invent exact competitor prices unless provided in data.")
        ai_text = result.text if result.ok else f"Local AI insight unavailable: {result.error}"

    sections = [
        card("Comparison KPIs", "<div class='grid'>" + "".join([
            kpi("Detected products/components", fmt_number(len(df), 0), "Across all readable sheets"),
            kpi("Comparison groups", fmt_number(group_summary["Compare group"].nunique(), 0), "Category or name-based"),
            kpi("Average unit cost", fmt_currency(df["Total unit cost"].dropna().mean(), currency), "Detected cost/component columns"),
            kpi("Average margin", fmt_pct(df["Margin %"].dropna().mean()), "Where price and cost exist"),
        ]) + "</div>"),
        card("Internal product/component groups", dataframe_table(group_summary, currency, numeric_currency_cols=["Unit price", "Total unit cost", "Handling", "Material", "Labor"], pct_cols=["Margin %"])),
        card("Product-level comparison", dataframe_table(df.sort_values("Margin %", ascending=False), currency, max_rows=120, numeric_currency_cols=["Unit price", "Total unit cost", "Material", "Labor", "Handling", "Overhead", "Margin/unit"], pct_cols=["Margin %"])),
        card("Market / competitor comparison", f"<p>{market_note}</p>{market_html}"),
    ]
    if ai_text:
        sections.append(card("Local AI comparison insight", f"<div class='ai-box'>{esc(ai_text)}</div>"))
    return render_page("Product & Component Comparison", f"Workbook: {workbook.filename}", sections, output_path)


def schema_report(workbook: WorkbookData, currency: str = "€", llm: Optional[OllamaClient] = None, output_path: Optional[str] = None) -> str:
    rows = []
    for t in workbook.tables:
        rows.append({
            "Sheet": t.name,
            "Rows": t.rows,
            "Columns": len(t.columns),
            "Detected roles": ", ".join(f"{role}: {match.column}" for role, match in (t.schema.roles.items() if t.schema else [])),
            "Score": t.schema.score if t.schema else 0,
            "Warnings": "; ".join(t.schema.warnings if t.schema else []),
        })
    df = pd.DataFrame(rows)
    ai_text = ""
    if llm:
        prompt = f"""
Review this arbitrary Excel workbook profile. Explain what business use cases appear possible and what columns/sheets are missing for invoices, quotations, margin analysis, production optimization and market comparison.

Workbook profile:
{workbook.compact_profile(max_rows_per_sheet=3)}
"""
        result = llm.generate(prompt, system="Return a concise schema-readiness assessment. Do not invent data.")
        ai_text = result.text if result.ok else f"Local AI schema assessment unavailable: {result.error}"
    sections = [card("Workbook/schema detection", dataframe_table(df, currency, pct_cols=[]))]
    if workbook.errors:
        sections.append(card("Read warnings", "<div class='warn'>" + esc("\n".join(workbook.errors)) + "</div>"))
    if ai_text:
        sections.append(card("Local AI schema assessment", f"<div class='ai-box'>{esc(ai_text)}</div>"))
    return render_page("Workbook Schema Report", f"Workbook: {workbook.filename}", sections, output_path)


def full_report(workbook: WorkbookData, currency: str = "€", llm: Optional[OllamaClient] = None, output_path: Optional[str] = None) -> str:
    """Combined report for management: schema, margins, production and comparison in one HTML file."""
    products = extract_products(workbook)
    df = products_to_dataframe(products)
    sections: List[str] = []

    if df.empty:
        sections.append(card(
            "No product data detected",
            "<p class='warn'>The workbook was read, but the tool could not confidently detect product/item rows with price, cost, quantity, or location data. Open the schema report to see detected sheets and column roles.</p>",
        ))
    else:
        valid_margin = df[df["Unit price"].notna() & df["Total unit cost"].notna()].copy()
        avg_margin = valid_margin["Margin %"].mean() if not valid_margin.empty else math.nan
        total_revenue = (valid_margin["Unit price"] * valid_margin["Quantity/demand"].fillna(1)).sum() if not valid_margin.empty else math.nan
        total_profit = (valid_margin["Margin/unit"] * valid_margin["Quantity/demand"].fillna(1)).sum() if not valid_margin.empty else math.nan
        best = valid_margin.sort_values("Margin %", ascending=False).head(8) if not valid_margin.empty else pd.DataFrame()
        worst = valid_margin.sort_values("Margin %", ascending=True).head(8) if not valid_margin.empty else pd.DataFrame()

        sections.append(card("Executive overview", "<div class='grid'>" + "".join([
            kpi("Products/components detected", fmt_number(len(df), 0), "Across readable sheets"),
            kpi("Average gross margin", fmt_pct(avg_margin), "Where price and cost exist"),
            kpi("Estimated revenue", fmt_currency(total_revenue, currency), "Uses quantity/demand if available"),
            kpi("Estimated profit", fmt_currency(total_profit, currency), "Workbook-derived estimate"),
        ]) + "</div>"))

        if not best.empty:
            sections.append(card("Strongest margins", bar_chart([(str(r["Product"] or r["SKU"]), float(r["Margin %"])) for _, r in best.iterrows()], "Top margins", currency, value_type="pct") + dataframe_table(best, currency, numeric_currency_cols=["Unit price", "Total unit cost", "Margin/unit"], pct_cols=["Margin %"])))
        if not worst.empty:
            sections.append(card("Margins needing attention", bar_chart([(str(r["Product"] or r["SKU"]), float(r["Margin %"])) for _, r in worst.iterrows()], "Lowest margins", currency, value_type="pct") + dataframe_table(worst, currency, numeric_currency_cols=["Unit price", "Total unit cost", "Margin/unit"], pct_cols=["Margin %"])))

        # Lightweight production section.
        loc_df = df[df["Location"].astype(str).str.strip() != ""].copy() if "Location" in df else pd.DataFrame()
        if not loc_df.empty and loc_df["Total unit cost"].notna().any():
            loc_summary = loc_df.groupby("Location", as_index=False).agg({
                "Total unit cost": ["mean", "min", "max"],
                "Material": "mean",
                "Labor": "mean",
                "Handling": "mean",
                "Overhead": "mean",
                "Quantity/demand": "sum",
            })
            loc_summary.columns = [" ".join(c).strip() for c in loc_summary.columns.to_flat_index()]
            loc_summary = loc_summary.sort_values("Total unit cost mean")
            sections.append(card("Production location cost comparison", bar_chart([(str(r["Location"]), float(r["Total unit cost mean"])) for _, r in loc_summary.head(10).iterrows()], "Average unit cost by location", currency, value_type="currency") + dataframe_table(loc_summary, currency, numeric_currency_cols=[c for c in loc_summary.columns if c != "Location"])))
        else:
            sections.append(card("Production location comparison", "<p class='warn'>No usable location + cost combination detected. Add plant/country/site and cost columns for production optimization.</p>"))

        # Internal grouping section.
        df["Compare group"] = df["Category"].where(df["Category"].astype(str).str.strip() != "", df["Product"].astype(str).str.lower().str.extract(r"([a-zA-Z]+)", expand=False).fillna("Ungrouped"))
        group_summary = df.groupby("Compare group", as_index=False).agg({
            "Product": "count",
            "Unit price": "mean",
            "Total unit cost": "mean",
            "Margin %": "mean",
            "Handling": "mean",
        }).rename(columns={"Product": "Products in group"}).sort_values("Margin %", ascending=False)
        sections.append(card("Product/component group comparison", dataframe_table(group_summary, currency, numeric_currency_cols=["Unit price", "Total unit cost", "Handling"], pct_cols=["Margin %"])))

    # Schema section always included.
    schema_rows = []
    for t in workbook.tables:
        schema_rows.append({
            "Sheet": t.name,
            "Rows": t.rows,
            "Columns": len(t.columns),
            "Detected roles": ", ".join(f"{role}: {match.column}" for role, match in (t.schema.roles.items() if t.schema else [])),
            "Score": t.schema.score if t.schema else 0,
        })
    sections.append(card("Workbook/schema detection", dataframe_table(pd.DataFrame(schema_rows), currency)))

    ai_text = ""
    if llm:
        compact = df.head(80).to_dict(orient="records") if not df.empty else []
        prompt = f"""
You are an AI business process, manufacturing, and margin analyst. Create an executive HTML-report narrative in plain text/bullets from this workbook-derived data.
Cover:
1. How production should be structured and what location/cost evidence supports it.
2. Which products have strongest/weakest margins and likely reasons.
3. How underperforming margins can be improved.
4. What additional data is required for stronger market comparison.
Do not invent exact live market prices. Use only data provided for numeric claims.

Workbook: {workbook.filename}
Detected schema: {workbook.schema_summary()}
Product sample: {compact}
"""
        result = llm.generate(prompt, system="Return concise executive recommendations with bullets and clear caveats. Do not output HTML tags.")
        ai_text = result.text if result.ok else f"Local AI executive summary unavailable: {result.error}"
    if ai_text:
        sections.insert(1, card("Local AI executive recommendations", f"<div class='ai-box'>{esc(ai_text)}</div>"))

    return render_page("Business Process AI Report", f"Workbook: {workbook.filename}", sections, output_path)


def generate_selected_document_from_form(
    workbook: WorkbookData,
    form: Dict[str, Any],
    document_type: str,
    currency: str = "€",
    llm: Optional[OllamaClient] = None,
    output_path: Optional[str] = None,
) -> str:
    products = extract_products(workbook)
    lines = _selected_lines_from_form(products, form)
    if not lines:
        # Select the first product as a friendly fallback, so users still see an output.
        if products:
            lines = [SelectedLine(products[0], 1.0)]
        else:
            lines = []
    company = str(form.get("company", "Your Company") or "Your Company")
    customer = str(form.get("customer", "Customer") or "Customer")
    notes = str(form.get("notes", "") or "")
    tax_rate = safe_number(form.get("tax_rate", 21), 21.0)

    ai_note = ""
    if llm and lines:
        prompt = f"""
Draft a short commercial note for this {document_type}. Mention value proposition, delivery/pricing assumptions, and any margin considerations that should be checked internally. Keep it professional and concise.
Lines: {[{'sku': l.product.sku, 'product': l.product.name, 'qty': l.quantity, 'unit_price': l.unit_price, 'cost': l.product.total_cost(), 'location': l.product.location} for l in lines]}
"""
        result = llm.generate(prompt, system="Do not make legal promises. Use concise business language.")
        ai_note = result.text if result.ok else ""

    return render_invoice_or_quote(
        document_type=document_type,
        lines=lines,
        company=company,
        customer=customer,
        currency=currency,
        tax_rate=tax_rate,
        notes=notes,
        output_path=output_path,
        llm_summary=ai_note,
    )
