from __future__ import annotations

import re

from src.listing.brand_term_extractor import extract_candidate_brand_terms
from src.schemas import ListingInput, ParsedListing

_RISK_PATTERNS = [
    r"compatible with",
    r"for\s+[A-Za-z0-9\-\s]{1,30}",
    r"[A-Za-z0-9\-\s]{1,30}\s+style",
    r"inspired by",
    r"replacement for",
    r"works with",
    r"similar to",
    r"look alike",
]


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _extract_product_terms(text: str, brand_terms: list[str]) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", text.lower())
    stop = {"the", "and", "with", "for", "to", "of", "in", "on", "a", "an", "is"}
    brand_bag = {b.lower() for b in brand_terms}
    result: list[str] = []
    for t in tokens:
        if t in stop or t in brand_bag or len(t) < 3:
            continue
        if t not in result:
            result.append(t)
    return result[:20]


def parse_listing(listing_input: ListingInput) -> ParsedListing:
    normalized_title = _normalize_text(listing_input.title)
    normalized_description = _normalize_text(listing_input.description)
    normalized_original_question = _normalize_text(listing_input.original_question)
    combined = f"{normalized_title} {normalized_description}".strip()

    brand_terms = extract_candidate_brand_terms(
        f"{normalized_title} {normalized_original_question}".strip(),
        normalized_description,
    )
    risk_patterns: list[str] = []
    for pattern in _RISK_PATTERNS:
        for m in re.finditer(pattern, combined, flags=re.IGNORECASE):
            phrase = _normalize_text(m.group(0))
            if phrase.lower() not in {x.lower() for x in risk_patterns}:
                risk_patterns.append(phrase)

    product_terms = _extract_product_terms(combined, brand_terms)

    return ParsedListing(
        normalized_title=normalized_title,
        normalized_description=normalized_description,
        inferred_category=_normalize_text(listing_input.category).lower(),
        title=normalized_title,
        description=normalized_description,
        category=_normalize_text(listing_input.category),
        platform=_normalize_text(listing_input.platform),
        has_authorization=listing_input.has_authorization,
        candidate_brand_terms=brand_terms,
        brand_terms=brand_terms,
        product_terms=product_terms,
        risk_patterns=risk_patterns,
    )
