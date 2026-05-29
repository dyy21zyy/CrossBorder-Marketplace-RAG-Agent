from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

DISCLAIMER_PATTERNS = [
    "preliminary ip risk screening",
    "does not constitute legal advice",
    "not legal advice",
    "本系统仅用于知识产权风险初筛，不构成法律意见",
    "不构成法律意见",
]

RELEVANCE_SECTIONS = {
    "overall_risk": ["overall risk", "总体风险", "整体风险"],
    "trademark_risk": ["trademark risk", "商标风险"],
    "platform_policy_risk": [
        "platform policy risk",
        "platform risk",
        "平台规则风险",
        "平台政策风险",
    ],
    "patent_claim_risk": [
        "patent claim risk",
        "patent risk",
        "专利权利要求风险",
        "专利风险",
    ],
    "litigation_risk": ["litigation risk", "诉讼历史风险", "诉讼风险"],
    "evidence_used": ["evidence used", "evidence", "使用的证据", "证据"],
    "listing_revision_suggestions": [
        "listing revision suggestions",
        "revision suggestions",
        "修改建议",
        "listing 修改建议",
    ],
    "disclaimer": ["disclaimer", "免责声明", "不构成法律意见"],
}

EVIDENCE_REQUIREMENTS = {
    "trademark_risk": {
        "keys": ["trademark_evidence"],
        "source_types": {"trademark", "rule_based_trademark"},
    },
    "platform_policy_risk": {
        "keys": ["platform_policy_evidence"],
        "source_types": {"platform_policy"},
    },
    "patent_claim_risk": {
        "keys": ["patent_claim_evidence"],
        "source_types": {"patent_claim"},
    },
    "litigation_risk": {
        "keys": ["litigation_evidence"],
        "source_types": {"litigation"},
    },
}

KNOWN_BRANDS = {
    "air max",
    "apple",
    "crocs",
    "disney",
    "dyson",
    "ipad",
    "iphone",
    "lego",
    "nike",
    "stanley",
    "samsung",
    "adidas",
}
ZH_REQUIRED_DISCLAIMER = "本系统仅用于知识产权风险初筛，不构成法律意见"
UNNECESSARY_ENGLISH_TEMPLATES = [
    "for daily use",
    "phone accessory",
    "daily use",
    "product listing",
    "listing revision suggestions",
    "overall risk",
    "trademark risk",
    "platform policy risk",
    "patent claim risk",
    "litigation risk",
]


def _load(path: str):
    return [
        json.loads(x)
        for x in Path(path).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def _level(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("risk_level", "unknown")
    return str(value or "unknown").strip().lower().replace("_", "-")


def _iter_evidence(evidence_bundle: dict, keys: Iterable[str] | None = None):
    for key, values in evidence_bundle.items():
        if keys is not None and key not in keys:
            continue
        if not key.endswith("_evidence") or not isinstance(values, list):
            continue
        for item in values:
            yield item


def _item_text(item: Any) -> str:
    if hasattr(item, "model_dump"):
        data = item.model_dump()
    elif isinstance(item, dict):
        data = item
    else:
        data = getattr(item, "__dict__", {})
    metadata = data.get("metadata", {}) or {}
    return " ".join(
        str(x or "")
        for x in [
            data.get("evidence_type"),
            data.get("source"),
            data.get("title"),
            data.get("snippet"),
            json.dumps(metadata, ensure_ascii=False),
        ]
    )


def _source_type(item: Any) -> str:
    if hasattr(item, "evidence_type"):
        return str(item.evidence_type or "").strip().lower()
    if isinstance(item, dict):
        return (
            str(item.get("evidence_type") or item.get("source_type") or "")
            .strip()
            .lower()
        )
    return ""


def _has_required_evidence(evidence_bundle: dict, dim: str) -> bool:
    req = EVIDENCE_REQUIREMENTS[dim]
    required_types = req["source_types"]
    for item in _iter_evidence(evidence_bundle, req["keys"]):
        st = _source_type(item)
        text = _item_text(item).lower()
        if st == "system":
            continue
        if st in required_types or any(
            source_type in text for source_type in required_types
        ):
            return True
    return False


def _citation_coverage(risk_result: dict, evidence_bundle: dict) -> float:
    dims = risk_result.get("dimension_risks", {})
    required = []
    for dim in EVIDENCE_REQUIREMENTS:
        if _level(dims.get(dim, "unknown")) != "unknown":
            required.append(dim)
    if not required:
        return 1.0
    return sum(
        1 for dim in required if _has_required_evidence(evidence_bundle, dim)
    ) / len(required)


def _answer_relevance(answer: str, expected_points: list[str]) -> float:
    ans = answer.lower()
    section_hits = sum(
        1
        for patterns in RELEVANCE_SECTIONS.values()
        if any(pattern.lower() in ans for pattern in patterns)
    )
    section_score = section_hits / len(RELEVANCE_SECTIONS)

    expected_hits = 0
    for point in expected_points:
        p = point.lower()
        if "trademark" in p and any(x in ans for x in ["trademark risk", "商标风险"]):
            expected_hits += 1
        elif ("iphone" in p or "apple" in p) and any(
            x in ans for x in ["iphone", "apple"]
        ):
            expected_hits += 1
        elif "does not claim infringement" in p and not any(
            x in ans
            for x in ["the product infringes", "definitely infringes", "确定侵权"]
        ):
            expected_hits += 1
        elif "disclaimer" in p and any(
            pattern.lower() in ans for pattern in DISCLAIMER_PATTERNS
        ):
            expected_hits += 1
        else:
            tokens = [t for t in re.findall(r"[a-z0-9\u4e00-\u9fff]+", p) if len(t) > 2]
            if tokens and all(t in ans for t in tokens[:2]):
                expected_hits += 1
    expected_score = expected_hits / max(1, len(expected_points))
    return max(section_score, 0.6 * section_score + 0.4 * expected_score)


def _is_chinese_text(text: str) -> bool:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return chinese > 0 and chinese >= latin * 0.5


def _is_chinese_input(sample: dict) -> bool:
    return any(
        _is_chinese_text(str(sample.get(key, "")))
        for key in ["question", "title", "description"]
    )


def _expected_brand_terms(sample: dict) -> list[str]:
    explicit = [
        str(x).strip() for x in sample.get("expected_brand_terms", []) if str(x).strip()
    ]
    if explicit:
        return explicit

    source_text = " ".join(
        str(sample.get(key, "")) for key in ["question", "title", "description"]
    )
    source_lower = source_text.lower()
    return [
        brand
        for brand in sorted(KNOWN_BRANDS, key=len, reverse=True)
        if brand in source_lower
    ]


def _brand_preservation(answer: str, sample: dict) -> int:
    brands = _expected_brand_terms(sample)
    if not brands:
        return 1
    answer_lower = answer.lower()
    return int(all(brand.lower() in answer_lower for brand in brands))


def _mixed_language_penalty(answer: str, sample: dict) -> int:
    if not _is_chinese_input(sample):
        return 0

    answer_lower = answer.lower()
    phrase_hits = sum(
        1 for phrase in UNNECESSARY_ENGLISH_TEMPLATES if phrase in answer_lower
    )
    latin_tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]*", answer)
    allowed_tokens = {
        token for brand in KNOWN_BRANDS for token in re.findall(r"[A-Za-z0-9]+", brand)
    }
    allowed_tokens.update(
        {"ip", "us", "uspto", "temu", "amazon", "ebay", "walmart", "tiktok", "llm"}
    )
    unnecessary_tokens = [
        token for token in latin_tokens if token.lower() not in allowed_tokens
    ]
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", answer))
    excessive_english = (
        len(unnecessary_tokens) >= 16 and len(unnecessary_tokens) > chinese_chars * 0.25
    )
    return int(phrase_hits >= 2 or excessive_english)


def _listing_from_sample(sample: dict):
    from src.listing.chinese_query_parser import parse_chinese_user_question
    from src.schemas import ListingInput

    question = str(sample.get("question", "")).strip()
    if not sample.get("title") and question:
        parsed = parse_chinese_user_question(question)
        return ListingInput(
            title=parsed["title"],
            description=parsed.get("description", ""),
            category=parsed.get("category", ""),
            platform=parsed.get("platform", sample.get("platform", "Temu")),
            has_authorization=bool(
                sample.get("has_authorization", parsed.get("has_authorization", False))
            ),
            original_question=question,
        )

    return ListingInput(
        title=sample.get("title") or question or "Cross-border marketplace product",
        description=sample.get("description", ""),
        category=sample.get("category", ""),
        platform=sample.get("platform", "Temu"),
        has_authorization=bool(sample.get("has_authorization", False)),
        original_question=question,
    )


def _is_negated_context(answer: str, start: int) -> bool:
    window = answer[max(0, start - 48) : start].lower()
    return any(
        phrase in window
        for phrase in [
            "no ",
            "not ",
            "does not ",
            "without ",
            "absence of ",
            "insufficient",
            "未检索",
            "没有",
            "无",
            "不构成",
        ]
    )


def _specific_claims(answer: str) -> dict[str, set[str]]:
    claims: dict[str, set[str]] = {
        "brands": set(),
        "patents": set(),
        "cases": set(),
        "platform_rules": set(),
    }
    lowered = answer.lower()
    for brand in KNOWN_BRANDS:
        for match in re.finditer(rf"\b{re.escape(brand)}\b", lowered):
            if not _is_negated_context(answer, match.start()):
                claims["brands"].add(brand)
    for match in re.finditer(r"\b(?:US\s*)?\d{7,}[A-Z0-9]*\b", answer, flags=re.I):
        prefix = answer[max(0, match.start() - 20) : match.start()].lower()
        if (
            "patent" in prefix
            or "专利" in prefix
            or match.group(0).lower().startswith("us")
        ) and not _is_negated_context(answer, match.start()):
            claims["patents"].add(re.sub(r"\s+", "", match.group(0)).lower())
    for match in re.finditer(
        r"\b[A-Z][A-Za-z0-9&.,' -]+\s+v\.\s+[A-Z][A-Za-z0-9&.,' -]+", answer
    ):
        if not _is_negated_context(answer, match.start()):
            claims["cases"].add(match.group(0).lower().strip())
    for match in re.finditer(
        r"\b(?:Temu|Amazon|eBay|Walmart|TikTok)\s+(?:IP|intellectual property|policy|rule|rules|平台规则|政策)\b",
        answer,
        flags=re.I,
    ):
        if not _is_negated_context(answer, match.start()):
            claims["platform_rules"].add(match.group(0).lower())
    return claims


def _unsupported_claim_rate(answer: str, evidence_bundle: dict) -> float:
    evidence_text = " ".join(
        _item_text(item) for item in _iter_evidence(evidence_bundle)
    ).lower()
    claims = _specific_claims(answer)
    total = sum(len(values) for values in claims.values())
    if total == 0:
        return 0.0
    unsupported = 0
    for values in claims.values():
        for claim in values:
            compact_claim = re.sub(r"\s+", "", claim)
            compact_evidence = re.sub(r"\s+", "", evidence_text)
            if claim not in evidence_text and compact_claim not in compact_evidence:
                unsupported += 1
    return unsupported / total


def evaluate_response(
    path="data/eval/response_eval.jsonl", use_llm_judge: bool = False
) -> dict[str, Any]:
    try:
        from src.agents.evidence_agent import EvidenceAgent
        from src.agents.final_answer_agent import FinalAnswerAgent
        from src.agents.query_router_agent import QueryRouter
        from src.agents.risk_judge_agent import RiskJudgeAgent
    except Exception as e:
        return {
            "per_sample": [],
            "metrics": {
                "faithfulness": 0.0,
                "unsupported_claim_rate": 1.0,
                "answer_relevance": 0.0,
                "disclaimer_coverage": 0.0,
                "forbidden_claim_rate": 0.0,
                "citation_coverage": 0.0,
                "chinese_answer_rate": 0.0,
                "chinese_disclaimer_coverage": 0.0,
                "brand_preservation": 0.0,
                "mixed_language_penalty": 1.0,
            },
            "warning": f"evaluation dependencies unavailable: {e}",
        }
    samples = _load(path)
    q = QueryRouter()
    e = EvidenceAgent()
    r = RiskJudgeAgent()
    f = FinalAnswerAgent()
    per = []
    for s in samples:
        li = _listing_from_sample(s)
        ev = e.collect(
            li,
            q.route(f"{li.title} {li.description}").get("intents", []),
            enable_patent_check=True,
            enable_litigation_check=True,
            use_reranker=False,
        )
        rr = r.judge(ev)
        answer_language = "zh" if _is_chinese_input(s) else "auto"
        answer = f.generate(li, ev, rr, [], answer_language=answer_language).summary
        ans_lower = answer.lower()
        expected = s.get("expected_answer_points", [])
        answer_relevance = _answer_relevance(answer, expected)
        disclaimer = int(
            any(pattern.lower() in ans_lower for pattern in DISCLAIMER_PATTERNS)
        )
        forbidden = s.get("forbidden_claims", [])
        forbidden_hits = 0
        for claim in forbidden:
            for match in re.finditer(re.escape(claim.lower()), ans_lower):
                if not _is_negated_context(answer, match.start()):
                    forbidden_hits += 1
        unsupported_rate = _unsupported_claim_rate(answer, ev)
        citation_cov = _citation_coverage(rr, ev)
        chinese_answer_rate = int(
            (not _is_chinese_input(s)) or _is_chinese_text(answer)
        )
        chinese_disclaimer_coverage = int(
            (not _is_chinese_input(s)) or (ZH_REQUIRED_DISCLAIMER in answer)
        )
        brand_preservation = _brand_preservation(answer, s)
        mixed_language_penalty = _mixed_language_penalty(answer, s)
        per.append(
            {
                "id": s["id"],
                "faithfulness": 1 - unsupported_rate,
                "unsupported_claim_rate": unsupported_rate,
                "answer_relevance": answer_relevance,
                "disclaimer_coverage": disclaimer,
                "forbidden_claim_rate": int(forbidden_hits > 0),
                "citation_coverage": citation_cov,
                "chinese_answer_rate": chinese_answer_rate,
                "chinese_disclaimer_coverage": chinese_disclaimer_coverage,
                "brand_preservation": brand_preservation,
                "mixed_language_penalty": mixed_language_penalty,
            }
        )
    n = max(1, len(per))
    metrics = {
        k: sum(x[k] for x in per) / n
        for k in [
            "faithfulness",
            "unsupported_claim_rate",
            "answer_relevance",
            "disclaimer_coverage",
            "forbidden_claim_rate",
            "citation_coverage",
            "chinese_answer_rate",
            "chinese_disclaimer_coverage",
            "brand_preservation",
            "mixed_language_penalty",
        ]
    }
    return {"per_sample": per, "metrics": metrics}
