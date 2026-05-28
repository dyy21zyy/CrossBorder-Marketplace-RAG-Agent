from __future__ import annotations

import re

KNOWN_BRANDS = {
    "apple", "iphone", "airpods", "disney", "marvel", "lego", "nike", "adidas", "stanley", "crocs",
    "barbie", "pokemon", "hello kitty", "samsung", "dyson", "gopro", "gucci", "prada", "chanel",
    "rolex", "nintendo", "playstation", "tesla", "bmw", "mercedes",
}

GENERIC_TERMS = {
    "case", "phone", "cover", "bag", "toy", "new", "fashion", "stand", "holder", "charger", "cable",
    "bottle", "cup", "backpack", "shoes", "clothing", "accessory", "compatible", "replacement",
}


def _norm_token(token: str) -> str:
    return re.sub(r"\s+", " ", token.strip())


def extract_candidate_brand_terms(title: str, description: str) -> list[str]:
    text = f"{title or ''} {description or ''}".strip()
    if not text:
        return []

    candidates: list[str] = []

    # 1) consecutive uppercase words
    for match in re.finditer(r"\b(?:[A-Z]{2,}(?:\s+[A-Z]{2,})*)\b", text):
        candidates.append(_norm_token(match.group(0)))

    # 2) capitalized/mixed brand-like words and short phrases
    for match in re.finditer(r"\b(?:[A-Z][a-z]+|[a-z]+[A-Z][A-Za-z0-9]*)\b(?:\s+(?:[A-Z][a-zA-Z0-9]+)){0,2}", text):
        candidates.append(_norm_token(match.group(0)))

    # 3) brand/product tokens with numbers and optional suffix
    for match in re.finditer(r"\b(?:[A-Z][a-zA-Z]+|[a-z]+[A-Z][A-Za-z]+)\s+\d{1,3}(?:\s+[A-Z][a-zA-Z0-9]+)?\b", text):
        candidates.append(_norm_token(match.group(0)))

    # 4) force keep known brand candidates
    lower_text = text.lower()
    for brand in KNOWN_BRANDS:
        if brand in lower_text:
            candidates.append(brand.title() if brand != "bmw" else "BMW")

    dedup: list[str] = []
    seen: set[str] = set()
    for cand in candidates:
        c = _norm_token(cand)
        c_low = c.lower()
        if not c:
            continue
        if c_low in GENERIC_TERMS:
            continue
        if len(c) <= 1:
            continue
        if c_low in seen:
            continue
        seen.add(c_low)
        dedup.append(c)
    return dedup
