from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from .schema_mapper import normalize_text

STOPWORDS = {
    "the", "and", "for", "with", "from", "product", "item", "part", "component", "unit", "piece", "pcs",
    "new", "old", "standard", "basic", "premium", "small", "large", "left", "right", "front", "back",
}
MATERIAL_WORDS = {
    "aluminium", "aluminum", "steel", "stainless", "plastic", "carbon", "fiber", "fibre", "wood", "rubber",
    "copper", "brass", "zinc", "glass", "nylon", "abs", "pp", "pe", "pvc", "polycarbonate",
}
DOMAIN_FAMILY_HINTS = {
    "bracket", "housing", "cover", "marine", "valve", "pump", "motor", "sensor", "cable", "connector",
    "panel", "frame", "mount", "pipe", "tube", "seal", "gasket", "filter", "adapter", "module",
}


def text_tokens(*values: Any) -> Set[str]:
    text = normalize_text(" ".join(str(v) for v in values if v is not None))
    raw = re.findall(r"[a-z0-9]+", text)
    return {t for t in raw if len(t) >= 3 and t not in STOPWORDS}


def extract_dimensions(text: Any) -> Set[str]:
    value = normalize_text(text)
    dims = set(re.findall(r"\b\d+(?:[.,]\d+)?\s?(?:mm|cm|m|kg|g|l|ml|inch|in)\b", value))
    dims.update(re.findall(r"\b\d+[x×]\d+(?:[x×]\d+)?\b", value))
    return {d.replace(" ", "") for d in dims}


def product_family(value: Any, category: Any = "", sku: Any = "") -> str:
    toks = text_tokens(category, value)
    if not toks and sku:
        return str(sku).split("-")[0].upper()
    hints = sorted((toks & DOMAIN_FAMILY_HINTS) or set())
    materials = sorted(toks & MATERIAL_WORDS)
    if hints and materials:
        return f"{materials[0]} {hints[0]}"
    if hints:
        return hints[0]
    if category and normalize_text(category):
        return normalize_text(category)
    # Stable fallback: first two alphabetic tokens.
    alpha = [t for t in sorted(toks) if not t.isdigit()]
    return " ".join(alpha[:2]) if alpha else (str(sku).split("-")[0].upper() if sku else "ungrouped")


def product_signature(value: Any, category: Any = "", sku: Any = "") -> Dict[str, Any]:
    toks = text_tokens(category, value, sku)
    return {
        "tokens": toks,
        "family": product_family(value, category, sku),
        "materials": toks & MATERIAL_WORDS,
        "dimensions": extract_dimensions(value),
        "sku_prefix": str(sku).split("-")[0].upper() if sku else "",
        "normalized": normalize_text(value),
    }


def match_score(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    a_tokens = set(a.get("tokens", set()))
    b_tokens = set(b.get("tokens", set()))
    union = a_tokens | b_tokens
    overlap = len(a_tokens & b_tokens) / max(1, len(union))
    seq = SequenceMatcher(None, str(a.get("normalized", "")), str(b.get("normalized", ""))).ratio()
    family_bonus = 0.18 if a.get("family") and a.get("family") == b.get("family") else 0.0
    material_bonus = 0.08 if set(a.get("materials", set())) & set(b.get("materials", set())) else 0.0
    dimension_bonus = 0.10 if set(a.get("dimensions", set())) & set(b.get("dimensions", set())) else 0.0
    sku_bonus = 0.08 if a.get("sku_prefix") and a.get("sku_prefix") == b.get("sku_prefix") else 0.0
    return min(1.0, overlap * 0.48 + seq * 0.34 + family_bonus + material_bonus + dimension_bonus + sku_bonus)


def build_token_index(signatures: Sequence[Dict[str, Any]]) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {}
    for i, sig in enumerate(signatures):
        for tok in sig.get("tokens", set()):
            index.setdefault(tok, []).append(i)
        fam = sig.get("family")
        if fam:
            index.setdefault(f"family:{fam}", []).append(i)
    return index


def candidate_indices(sig: Dict[str, Any], index: Dict[str, List[int]], max_per_token: int = 1500, fallback_size: int = 2000) -> List[int]:
    ids: Set[int] = set()
    for tok in sig.get("tokens", set()):
        ids.update(index.get(tok, [])[:max_per_token])
    fam = sig.get("family")
    if fam:
        ids.update(index.get(f"family:{fam}", [])[:max_per_token])
    if not ids:
        return list(range(fallback_size))
    return list(ids)
