from __future__ import annotations

import re
from collections.abc import Iterable

DEFAULT_TITLE = "Cross-border marketplace product"
DEFAULT_DESCRIPTION = "Product listing described by the user"

_PLATFORM_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Temu", ("Temu", "temu", "特姆", "拼多多海外版")),
)

_MARKET_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("EU", ("欧盟", "欧洲", "EU", "eu", "EUIPO", "EUTM", "RCD", "TMclass", "euipo", "eutm", "rcd", "tmclass")),
    ("US", ("美国站", "美国", "USA", "US", "usa", "us")),
)

_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("phone accessory", ("手机壳", "保护壳", "手机支架", "支架")),
    ("shoes", ("运动鞋", "鞋")),
    ("toys", ("玩具", "积木")),
    ("cups", ("保温杯", "水杯")),
    ("bags", ("背包", "包")),
)

_AUTH_TRUE_TERMS = ("官方授权", "已授权", "有授权")
_AUTH_FALSE_TERMS = ("没有授权", "无授权", "未授权")
_PATENT_TERMS = ("专利", "claim", "权利要求", "结构", "折叠", "磁吸", "支架", "机械", "mechanism")
_LITIGATION_TERMS = ("诉讼", "起诉", "案件", "litigation", "lawsuit")

_PRODUCT_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("phone case", ("手机壳", "保护壳")),
    ("phone stand", ("手机支架", "支架")),
    ("sneakers", ("运动鞋",)),
    ("shoes", ("鞋",)),
    ("building block toy", ("积木",)),
    ("toy", ("玩具",)),
    ("insulated cup", ("保温杯",)),
    ("cup", ("水杯",)),
    ("backpack", ("背包",)),
    ("bag", ("包",)),
)

_FEATURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("transparent", ("透明",)),
    ("magnetic", ("磁吸",)),
    ("foldable", ("折叠",)),
    ("mechanical", ("机械",)),
)


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _first_rule_match(text: str, rules: tuple[tuple[str, tuple[str, ...]], ...], default: str = "") -> str:
    for value, terms in rules:
        if _contains_any(text, terms):
            return value
    return default


def _extract_device(question: str) -> str:
    match = re.search(r"iPhone\s*\d{1,2}(?:\s*(?:Pro|Plus|Max|Mini|pro|plus|max|mini))*", question, flags=re.IGNORECASE)
    if match:
        compact = re.sub(r"\s+", " ", match.group(0)).strip()
        return compact[0].lower() + compact[1:] if compact.lower().startswith("iphone") else compact
    return ""


def _build_english_listing_text(question: str) -> tuple[str, str]:
    product_type = _first_rule_match(question, _PRODUCT_TYPE_RULES, default="product")
    device = _extract_device(question)
    features = [english for english, terms in _FEATURE_RULES if _contains_any(question, terms)]

    if device and product_type == "phone case":
        title = f"Phone case compatible with {device}"
        description_features = " ".join(features)
        description = f"{description_features} phone case for {device}" if description_features else f"Phone case for {device}"
        return title, description[0].upper() + description[1:]

    title_parts = [*features, product_type]
    title = " ".join(title_parts).strip() or DEFAULT_TITLE
    if device:
        title = f"{title} compatible with {device}"
    title = title[0].upper() + title[1:]

    description = title
    if product_type == "product" and not features and not device:
        description = DEFAULT_DESCRIPTION
    return title, description


def parse_chinese_user_question(question: str) -> dict:
    """Parse a Chinese natural-language marketplace/IP-risk question into listing fields."""
    normalized_question = re.sub(r"\s+", " ", (question or "").strip())
    title, description = _build_english_listing_text(normalized_question)

    return {
        "title": title,
        "description": description,
        "category": _first_rule_match(normalized_question, _CATEGORY_RULES),
        "platform": _first_rule_match(normalized_question, _PLATFORM_RULES),
        "has_authorization": _contains_any(normalized_question, _AUTH_TRUE_TERMS)
        if not _contains_any(normalized_question, _AUTH_FALSE_TERMS)
        else False,
        "enable_patent_check": _contains_any(normalized_question, _PATENT_TERMS),
        "enable_litigation_check": _contains_any(normalized_question, _LITIGATION_TERMS),
        "original_question": normalized_question,
        "language": "zh",
        "market": _first_rule_match(normalized_question, _MARKET_RULES, default="US"),
    }
