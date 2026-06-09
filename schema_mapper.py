from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r"[^a-z0-9%€$£_ /.-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


ROLE_SYNONYMS: Dict[str, List[str]] = {
    "sku": [
        "sku", "stock keeping unit", "item code", "item no", "item number", "article", "article no",
        "part no", "part number", "product code", "product id", "code", "id", "ref", "reference",
    ],
    "product": [
        "product", "product name", "item", "item name", "description", "name", "component", "component name",
        "material", "material name", "article name", "title", "part", "part name", "service",
    ],
    "category": ["category", "family", "group", "type", "class", "segment", "range", "product group"],
    "quantity": [
        "quantity", "qty", "units", "amount", "volume", "order qty", "order quantity", "sold", "sales volume",
        "production volume", "demand", "forecast", "annual demand", "monthly demand", "pieces", "pcs",
    ],
    "capacity": ["capacity", "max capacity", "available capacity", "plant capacity", "monthly capacity", "annual capacity"],
    "unit_price": [
        "price", "unit price", "sales price", "selling price", "sell price", "sale price", "net price", "gross price",
        "revenue per unit", "list price", "customer price", "market price", "target price", "quotation price",
    ],
    "unit_cost": [
        "cost", "unit cost", "production cost", "manufacturing cost", "purchase cost", "buy price", "cogs",
        "standard cost", "landed cost", "total cost", "cost price", "base cost", "factory cost",
    ],
    "material_cost": [
        "material cost", "raw material", "raw material cost", "materials", "ingredient cost", "component cost",
        "bom cost", "bill of material", "resin", "steel", "plastic", "input cost",
    ],
    "labor_cost": ["labor", "labour", "labor cost", "labour cost", "wages", "direct labor", "direct labour", "manhour", "man hour"],
    "handling_cost": [
        "handling", "handling cost", "warehouse", "warehousing", "storage", "picking", "packing", "inbound", "outbound",
        "logistics", "freight", "shipping", "transport", "customs", "duty", "tariff", "distribution",
    ],
    "overhead_cost": ["overhead", "overhead cost", "fixed cost", "utilities", "rent", "admin", "indirect cost", "depreciation"],
    "location": [
        "location", "country", "region", "plant", "factory", "site", "production location", "origin", "warehouse", "facility",
    ],
    "supplier": ["supplier", "vendor", "manufacturer", "producer", "source"],
    "customer": ["customer", "client", "buyer", "account", "company", "customer name"],
    "competitor": ["competitor", "brand", "market", "marketplace", "external", "benchmark"],
    "margin": ["margin", "gross margin", "profit margin", "gm", "margin %", "markup", "profit %"],
    "discount": ["discount", "rebate", "deduction"],
    "tax": ["tax", "vat", "btw", "sales tax"],
    "currency": ["currency", "curr", "ccy"],
    "lead_time": ["lead time", "delivery time", "days", "weeks", "lt", "production time"],
    "date": ["date", "invoice date", "quote date", "order date", "valid until", "validity"],
}

NUMERIC_ROLES = {
    "quantity", "capacity", "unit_price", "unit_cost", "material_cost", "labor_cost", "handling_cost",
    "overhead_cost", "margin", "discount", "tax", "lead_time",
}
STRING_ROLES = {"sku", "product", "category", "location", "supplier", "customer", "competitor", "currency", "date"}
COST_ROLES = ["unit_cost", "material_cost", "labor_cost", "handling_cost", "overhead_cost"]


@dataclass
class ColumnMatch:
    role: str
    column: str
    score: float
    reason: str = ""


@dataclass
class TableSchema:
    sheet_name: str
    columns: List[str]
    roles: Dict[str, ColumnMatch] = field(default_factory=dict)
    score: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def role_column(self, role: str) -> Optional[str]:
        match = self.roles.get(role)
        return match.column if match else None

    def as_simple_dict(self) -> Dict[str, str]:
        return {role: match.column for role, match in self.roles.items()}


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    a_c = compact_key(a)
    b_c = compact_key(b)
    if a_n == b_n or a_c == b_c:
        return 1.0
    if b_n in a_n or a_n in b_n:
        # Inclusion is useful but can overmatch short words like "id".
        shorter = min(len(a_c), len(b_c))
        if shorter <= 2:
            return 0.55
        return 0.88 if shorter >= 5 else 0.72
    token_overlap = len(set(a_n.split()) & set(b_n.split()))
    if token_overlap:
        return min(0.82, 0.45 + 0.16 * token_overlap)
    return SequenceMatcher(None, a_c, b_c).ratio() * 0.82


def _series_numeric_ratio(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    cleaned = series.dropna().head(100)
    if cleaned.empty:
        return 0.0
    converted = cleaned.apply(parse_number)
    return float(converted.notna().sum()) / max(1, len(cleaned))


def _series_text_ratio(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    cleaned = series.dropna().head(100)
    if cleaned.empty:
        return 0.0
    text_like = 0
    for value in cleaned:
        s = normalize_text(value)
        if s and not parse_number(s) == parse_number(s):  # NaN check for non-number
            text_like += 1
        elif re.search(r"[a-zA-Z]", str(value)):
            text_like += 1
    return text_like / max(1, len(cleaned))


def infer_schema(df: pd.DataFrame, sheet_name: str = "Sheet") -> TableSchema:
    columns = [str(c) for c in df.columns]
    schema = TableSchema(sheet_name=sheet_name, columns=columns)
    candidates: List[ColumnMatch] = []

    for col in columns:
        normalized_col = normalize_text(col)
        if not normalized_col or normalized_col.startswith("unnamed"):
            continue
        series = df[col] if col in df.columns else pd.Series(dtype=object)
        num_ratio = _series_numeric_ratio(series)
        text_ratio = _series_text_ratio(series)
        for role, synonyms in ROLE_SYNONYMS.items():
            best_syn = ""
            best_score = 0.0
            for synonym in synonyms:
                score = _similarity(normalized_col, synonym)
                if score > best_score:
                    best_score = score
                    best_syn = synonym
            # Data type signal.
            if role in NUMERIC_ROLES:
                best_score += 0.10 * num_ratio
                if text_ratio > 0.80 and num_ratio < 0.30:
                    best_score -= 0.18
            elif role in STRING_ROLES:
                best_score += 0.08 * text_ratio
                if num_ratio > 0.85 and role not in {"sku", "date"}:
                    best_score -= 0.16
            if role == "unit_price" and any(t in normalized_col for t in ["sell", "sales", "revenue", "price"]):
                best_score += 0.08
            if role == "unit_cost" and any(t in normalized_col for t in ["cost", "cogs", "landed"]):
                best_score += 0.08
            if role == "product" and normalized_col in {"description", "desc"}:
                best_score += 0.08
            if best_score >= 0.58:
                candidates.append(ColumnMatch(role=role, column=col, score=round(best_score, 3), reason=f"matched '{best_syn}'"))

    # Select best column per role, while avoiding assigning same column to too many roles where possible.
    candidates.sort(key=lambda c: c.score, reverse=True)
    used_columns: set[str] = set()
    for cand in candidates:
        current = schema.roles.get(cand.role)
        if current and current.score >= cand.score:
            continue
        # Permit a numeric cost column to be both total cost and material only if names demand it? Prefer unique.
        if cand.column in used_columns and cand.role not in {"sku", "product"}:
            continue
        schema.roles[cand.role] = cand
        used_columns.add(cand.column)

    # Add fallback product column: first text-rich column if product not found.
    if "product" not in schema.roles and columns:
        best_text: Tuple[float, Optional[str]] = (0.0, None)
        for col in columns:
            ratio = _series_text_ratio(df[col])
            name = normalize_text(col)
            if name.startswith("unnamed"):
                continue
            if ratio > best_text[0]:
                best_text = (ratio, col)
        if best_text[1] and best_text[0] >= 0.45:
            schema.roles["product"] = ColumnMatch("product", best_text[1], 0.51, "fallback: text-rich column")
            schema.warnings.append(f"Used '{best_text[1]}' as product/name fallback.")

    # Add fallback SKU/code column from short unique strings.
    if "sku" not in schema.roles:
        best_uniqueness: Tuple[float, Optional[str]] = (0.0, None)
        for col in columns:
            series = df[col].dropna().head(500)
            if len(series) < 2:
                continue
            text_ratio = _series_text_ratio(series)
            unique_ratio = series.astype(str).nunique() / max(1, len(series))
            avg_len = series.astype(str).map(len).mean()
            score = unique_ratio * 0.55 + text_ratio * 0.25 + (0.2 if avg_len <= 30 else 0.0)
            if score > best_uniqueness[0]:
                best_uniqueness = (score, col)
        if best_uniqueness[1] and best_uniqueness[0] >= 0.67:
            schema.roles["sku"] = ColumnMatch("sku", best_uniqueness[1], round(best_uniqueness[0], 3), "fallback: unique identifier-like column")

    # Compute table score for business usefulness.
    score = 0.0
    for role, weight in {
        "product": 2.0,
        "sku": 1.0,
        "unit_price": 2.2,
        "unit_cost": 2.2,
        "material_cost": 1.2,
        "labor_cost": 1.0,
        "handling_cost": 1.0,
        "location": 1.4,
        "quantity": 1.2,
        "capacity": 1.2,
        "competitor": 1.0,
        "margin": 1.4,
    }.items():
        if role in schema.roles:
            score += weight * min(1.0, schema.roles[role].score)
    if len(df) > 0:
        score += min(1.0, math.log10(len(df) + 1) / 3.0)
    schema.score = round(score, 3)
    return schema


def parse_number(value: Any) -> float:
    """Parse numbers from messy Excel cells. Returns NaN on failure."""
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return float(value)
        except Exception:
            return float("nan")
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "-"}:
        return float("nan")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    # Remove common currency symbols and words, keep separators, minus and percent.
    percent = "%" in s
    s = re.sub(r"[€$£¥]|eur|usd|gbp|aud|cad|chf|sek|nok|dkk", "", s, flags=re.I)
    s = re.sub(r"[^0-9,.-]+", "", s)
    if not s or s in {"-", ".", ","}:
        return float("nan")
    # Handle European decimal comma vs thousands comma.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[-1]) in {1, 2, 3}:
            # Ambiguous: 1,234 might be thousand or decimal. Treat 2 decimals as decimal, 3 as thousands.
            if len(parts[-1]) == 3 and len(parts[0]) <= 3:
                s = "".join(parts)
            else:
                s = s.replace(",", ".")
        else:
            s = "".join(parts)
    try:
        out = float(s)
        if negative:
            out = -out
        if percent:
            out = out / 100.0
        return out
    except Exception:
        return float("nan")


def is_number(value: Any) -> bool:
    n = parse_number(value)
    return n == n


def safe_number(value: Any, default: float = 0.0) -> float:
    n = parse_number(value)
    return default if n != n else n


def first_existing(mapping: Dict[str, ColumnMatch], roles: Iterable[str]) -> Optional[str]:
    for role in roles:
        if role in mapping:
            return mapping[role].column
    return None
