from __future__ import annotations

import re

from src.utils.language import detect_language

BRAND_TERMS: tuple[str, ...] = (
    "iPhone",
    "Apple",
    "Nike",
    "LEGO",
    "Disney",
    "Stanley",
    "Crocs",
    "AirPods",
    "Samsung",
    "Dyson",
    "GoPro",
)

# Longer/specific Chinese phrases must appear before shorter phrases so
# "透明手机壳" is rewritten as one concept before the generic "手机壳" rule.
ZH_TO_EN_RULES: tuple[tuple[str, str], ...] = (
    ("透明磁吸手机壳", "transparent phone case magnetic"),
    ("透明手机壳", "transparent phone case"),
    ("手机支架", "phone stand phone holder"),
    ("指环支架", "ring holder"),
    ("保温杯", "tumbler cup"),
    ("手机壳", "phone case"),
    ("水杯", "tumbler cup"),
    ("仿款", "style inspired by"),
    ("同款", "style inspired by"),
    ("风格", "style inspired by"),
    ("磁吸", "magnetic"),
    ("折叠", "foldable"),
    ("运动鞋", "running shoes"),
    ("积木", "building blocks"),
    ("背包", "backpack"),
    ("侵权", "infringement"),
    ("商标", "trademark"),
    ("专利", "patent"),
    ("投诉", "complaint"),
    ("下架", "takedown"),
    ("授权", "authorization"),
    ("适用于", "compatible with"),
)

_EXTRA_CONTEXT_RULES: tuple[tuple[str, str], ...] = (
    ("Temu", "Temu IP policy marketplace"),
    ("美国站", "US"),
    ("没有", "no"),
    ("无", "no"),
    ("未", "no"),
    ("风险", "risk"),
)


def extract_preserved_brand_terms(text: str) -> list[str]:
    """Return known brand tokens as they appear in the user text.

    Canonical casing from ``BRAND_TERMS`` is used so downstream trademark
    retrieval receives stable brand strings (for example ``iPhone`` instead of
    ``Iphone``).
    """
    found: list[str] = []
    for brand in BRAND_TERMS:
        if re.search(
            rf"(?<![A-Za-z0-9]){re.escape(brand)}(?![A-Za-z0-9])",
            text or "",
            flags=re.IGNORECASE,
        ):
            found.append(brand)
    return found


def _extract_model_phrases(text: str) -> list[str]:
    models: list[str] = []
    patterns = [
        r"iPhone\s*\d{1,2}(?:\s*(?:Pro|Plus|Max|Mini|pro|plus|max|mini))*",
        r"AirPods(?:\s*(?:Pro|Max|pro|max|\d{1,2}))*",
        r"Samsung\s+[A-Za-z]*\s*\d{1,3}(?:\s*[A-Za-z]+)?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            phrase = re.sub(r"\s+", " ", match.group(0)).strip()
            if phrase and phrase.lower() not in {x.lower() for x in models}:
                models.append(phrase)
    return models


def _append_unique(parts: list[str], value: str) -> None:
    normalized = re.sub(r"\s+", " ", value.strip())
    if normalized and normalized.lower() not in {part.lower() for part in parts}:
        parts.append(normalized)


def rewrite_query_for_retrieval(text: str, target_language: str = "en") -> str:
    """Rewrite a user query into the retrieval language.

    The current implementation is rule-based and optimized for Chinese input
    against English source collections. English input is normalized and returned
    unchanged when the target language is English.
    """
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if target_language != "en" or detect_language(normalized) != "zh":
        return normalized

    parts: list[str] = []
    for zh, en in ZH_TO_EN_RULES:
        if zh in normalized:
            _append_unique(parts, en)
    for needle, en in _EXTRA_CONTEXT_RULES:
        if needle.lower() in normalized.lower():
            _append_unique(parts, en)
    for model in _extract_model_phrases(normalized):
        _append_unique(parts, model)
    for brand in extract_preserved_brand_terms(normalized):
        _append_unique(parts, brand)

    return " ".join(parts) if parts else normalized
