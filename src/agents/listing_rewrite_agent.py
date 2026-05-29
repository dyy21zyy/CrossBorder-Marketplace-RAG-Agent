from __future__ import annotations

import re

from src.agents.llm_client import LLMClient
from src.schemas import ListingInput

EN_BANNED = [
    "style",
    "inspired by",
    "look alike",
    "replica",
    "dupe",
    "fake",
    "official",
    "authorized",
    "genuine",
    "authentic",
]
ZH_BANNED = ["仿款", "同款", "平替", "高仿", "复刻", "山寨", "官方", "正品", "授权"]

EN_REPLACEMENTS = [
    (r"\bi\s*phone\s*15\b", "selected 6.1-inch smartphone models"),
    (r"\bi\s*phone\b", "smartphone"),
    (r"\bapple\b", "smartphone brand"),
    (r"\bair\s*pods\b", "wireless earbuds"),
    (r"\blego\b", "interlocking building blocks"),
    (r"\bnike\b", "running shoes"),
    (r"\bdisney\b", "cartoon-style"),
    (r"\bstanley\b", "tumbler"),
    (r"\bcrocs\b", "clogs"),
]

ZH_REPLACEMENTS = [
    (r"i\s*phone\s*15", "部分 6.1 英寸机型"),
    (r"i\s*phone", "智能手机"),
    (r"apple", "智能设备品牌"),
    (r"air\s*pods", "无线耳机"),
    (r"lego", "拼插积木"),
    (r"nike", "运动鞋"),
    (r"disney", "卡通图案"),
    (r"stanley", "保温杯"),
    (r"crocs", "洞洞鞋"),
]

AUTH_COMPATIBLE_BRANDS = [
    (r"\bi\s*phone\s*15\b", "iPhone 15"),
    (r"\bi\s*phone\b", "iPhone"),
    (r"\bair\s*pods\b", "AirPods"),
    (r"\blego\b", "LEGO"),
    (r"\bnike\b", "Nike"),
    (r"\bdisney\b", "Disney"),
    (r"\bstanley\b", "Stanley"),
    (r"\bcrocs\b", "Crocs"),
]


class ListingRewriteAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    def _is_chinese(self, text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _remove_banned(self, title: str, is_chinese: bool) -> str:
        out = title
        for phrase in EN_BANNED:
            out = re.sub(rf"\b{re.escape(phrase)}\b", "", out, flags=re.IGNORECASE)
        if is_chinese:
            for phrase in ZH_BANNED:
                out = out.replace(phrase, "")
        return self._normalize_spacing(out)

    def _normalize_spacing(self, title: str) -> str:
        out = re.sub(r"\s+", " ", title)
        out = re.sub(r"\s+([,，。；;:：])", r"\1", out)
        out = re.sub(r"([（(])\s+", r"\1", out)
        out = re.sub(r"\s+([）)])", r"\1", out)
        out = re.sub(r"\s+的\s+", "的", out)
        out = re.sub(r"\s+", " ", out)
        return out.strip(" -_,，、")

    def _replace_brands(self, title: str, is_chinese: bool) -> str:
        replacements = ZH_REPLACEMENTS if is_chinese else EN_REPLACEMENTS
        out = title
        for pattern, replacement in replacements:
            out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
        return self._normalize_spacing(out)

    def _extract_candidate_brand_terms(self, evidence_bundle: dict) -> list[str]:
        parsed = evidence_bundle.get("parsed_listing") if evidence_bundle else None
        if not parsed:
            return []
        if isinstance(parsed, dict):
            return parsed.get("candidate_brand_terms", []) or []
        return getattr(parsed, "candidate_brand_terms", []) or []

    def _remove_candidate_brand_terms(self, title: str, evidence_bundle: dict) -> str:
        out = title
        for brand_term in self._extract_candidate_brand_terms(evidence_bundle):
            if not brand_term:
                continue
            out = re.sub(rf"\b{re.escape(brand_term)}\b", "", out, flags=re.IGNORECASE)
        return self._normalize_spacing(out)

    def _authorized_title(self, title: str, is_chinese: bool) -> str | None:
        if is_chinese:
            for pattern, brand in AUTH_COMPATIBLE_BRANDS:
                if re.search(pattern, title, flags=re.IGNORECASE):
                    if re.search(r"手机壳|保护壳|case", title, flags=re.IGNORECASE):
                        return f"兼容 {brand} 的第三方手机保护壳"
                    return f"兼容 {brand} 的第三方配件"
            return None

        for pattern, brand in AUTH_COMPATIBLE_BRANDS:
            if re.search(pattern, title, flags=re.IGNORECASE):
                if re.search(r"case|phone", title, flags=re.IGNORECASE):
                    return f"Third-party phone case compatible with {brand}"
                return f"Third-party accessory compatible with {brand}"
        return None

    def _phone_case_suggestions(
        self, title: str, is_chinese: bool, has_authorization: bool
    ) -> list[dict]:
        mentions_iphone_15 = re.search(r"i\s*phone\s*15", title, flags=re.IGNORECASE)
        mentions_phone_case = re.search(
            r"手机壳|保护壳|phone\s*case|case", title, flags=re.IGNORECASE
        )
        mentions_magnetic = re.search(r"磁吸|magnetic", title, flags=re.IGNORECASE)
        mentions_transparent = re.search(
            r"透明|transparent|clear", title, flags=re.IGNORECASE
        )
        if not (mentions_iphone_15 and mentions_phone_case):
            return []

        if is_chinese:
            first = (
                "透明磁吸手机保护壳"
                if mentions_transparent and mentions_magnetic
                else "手机保护壳"
            )
            second = "适用于部分 6.1 英寸机型的手机保护壳"
            third = "通用磁吸手机壳" if mentions_magnetic else "通用手机保护壳"
            suggestions = [
                {"title": first, "reason": "去除了第三方品牌词，改为功能性描述。"},
                {"title": second, "reason": "使用通用机型描述，降低品牌关联表达。"},
                {"title": third, "reason": "保留商品功能，避免暗示官方授权。"},
            ]
            if has_authorization:
                suggestions[1] = {
                    "title": "兼容 iPhone 15 的第三方手机保护壳",
                    "reason": "已有授权时可使用谨慎的兼容性表述，但避免官方、正品等表述。",
                }
            return suggestions

        first = (
            "Transparent magnetic phone case"
            if mentions_transparent and mentions_magnetic
            else "Protective phone case"
        )
        second = (
            "Magnetic phone case for selected 6.1-inch smartphone models"
            if mentions_magnetic
            else "Phone case for selected 6.1-inch smartphone models"
        )
        third = (
            "Universal magnetic protective phone case"
            if mentions_magnetic
            else "Universal protective phone case"
        )
        suggestions = [
            {
                "title": first,
                "reason": "Removed third-party brand terms and used function-focused wording.",
            },
            {
                "title": second,
                "reason": "Uses a generic model-size description to reduce brand association.",
            },
            {
                "title": third,
                "reason": "Keeps the product function without implying official authorization.",
            },
        ]
        if has_authorization:
            suggestions[1] = {
                "title": "Third-party phone case compatible with iPhone 15",
                "reason": "Authorization allows cautious compatibility wording, while avoiding official or authenticity claims.",
            }
        return suggestions

    def _generic_suggestions(
        self, title: str, listing: ListingInput, is_chinese: bool, evidence_bundle: dict
    ) -> list[dict]:
        sanitized = self._replace_brands(
            self._remove_banned(title, is_chinese), is_chinese
        )
        if not listing.has_authorization:
            sanitized = self._remove_candidate_brand_terms(sanitized, evidence_bundle)
        sanitized = self._normalize_spacing(sanitized)

        if is_chinese:
            base = sanitized or "通用商品标题"
            base = re.sub(r"cartoon", "卡通", base, flags=re.IGNORECASE)
            base = self._normalize_spacing(base)
            return [
                {
                    "title": base,
                    "reason": "去除或替换高风险品牌和授权相关表达，保留商品属性。",
                },
                {
                    "title": f"通用{base}" if not base.startswith("通用") else base,
                    "reason": "使用通用描述，减少与特定品牌的关联。",
                },
                {
                    "title": self._normalize_spacing(
                        f"{base}{listing.category}"
                        if listing.category and listing.category not in base
                        else base
                    ),
                    "reason": "补充品类信息，同时避免暗示官方授权。",
                },
            ]

        base = sanitized or "Generic product title"
        return [
            {
                "title": base,
                "reason": "Removed or replaced high-risk brand and authorization wording while preserving product attributes.",
            },
            {
                "title": f"{base} for everyday use",
                "reason": "Uses neutral function-focused phrasing and reduces brand association.",
            },
            {
                "title": self._normalize_spacing(
                    f"{base} {listing.category}"
                    if listing.category and listing.category.lower() not in base.lower()
                    else base
                ),
                "reason": "Adds category context while avoiding misleading authorization language.",
            },
        ]

    def _clean_suggestions(
        self, suggestions: list[dict], is_chinese: bool
    ) -> list[dict]:
        cleaned = []
        for suggestion in suggestions:
            title = self._normalize_spacing(suggestion.get("title", ""))
            if not title:
                continue
            lower_title = title.lower()
            if any(
                re.search(rf"\b{re.escape(term)}\b", lower_title) for term in EN_BANNED
            ):
                continue
            if is_chinese and any(term in title for term in ZH_BANNED):
                continue
            if any(existing["title"].lower() == lower_title for existing in cleaned):
                continue
            reason = suggestion.get("reason", "")
            if not reason:
                reason = (
                    "已降低高风险品牌和授权相关表达。"
                    if is_chinese
                    else "Reduced high-risk brand and authorization wording."
                )
            cleaned.append({"title": title, "reason": reason})
        return cleaned[:3]

    def rewrite(
        self, listing: ListingInput, risk_result: dict, evidence_bundle: dict
    ) -> list[dict]:
        is_chinese = self._is_chinese(f"{listing.title} {listing.description}")
        title = self._remove_banned(listing.title, is_chinese)

        suggestions = self._phone_case_suggestions(
            title, is_chinese, listing.has_authorization
        )
        if not suggestions:
            if listing.has_authorization:
                authorized_title = self._authorized_title(title, is_chinese)
                if authorized_title:
                    generic = self._generic_suggestions(
                        title, listing, is_chinese, evidence_bundle
                    )
                    suggestions = [
                        {
                            "title": authorized_title,
                            "reason": (
                                "已有授权时可使用谨慎的兼容性表述，但避免官方、正品等表述。"
                                if is_chinese
                                else "Authorization allows cautious compatibility wording, while avoiding official or authenticity claims."
                            ),
                        }
                    ] + generic[:2]
                else:
                    suggestions = self._generic_suggestions(
                        title, listing, is_chinese, evidence_bundle
                    )
            else:
                suggestions = self._generic_suggestions(
                    title, listing, is_chinese, evidence_bundle
                )

        return self._clean_suggestions(suggestions, is_chinese)
