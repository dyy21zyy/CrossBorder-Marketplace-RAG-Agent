from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

RISK_FIELDS = [
    ("trademark_risk", "expected_trademark_risk"),
    ("platform_policy_risk", "expected_platform_policy_risk"),
    ("patent_claim_risk", "expected_patent_claim_risk"),
    ("litigation_risk", "expected_litigation_risk"),
]
HIGH_EQUIVALENT = {"high", "medium-high"}
UNKNOWN_CORRECT = {"unknown", "low"}


def _load(path: str):
    return [
        json.loads(x)
        for x in Path(path).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def _normalize_level(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("risk_level", "unknown")
    text = str(value or "unknown").strip().lower().replace("_", "-")
    if text in {"mediumhigh", "med-high", "medium high"}:
        return "medium-high"
    return text


def _level_correct(expected: Any, predicted: Any) -> bool:
    exp = _normalize_level(expected)
    pred = _normalize_level(predicted)
    if exp == "high":
        return pred in HIGH_EQUIVALENT
    if exp == "unknown":
        return pred in UNKNOWN_CORRECT
    return pred == exp


def _confusion_matrix(
    rows: list[dict[str, Any]], dim: str
) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        expected = _normalize_level(row[f"expected_{dim}"])
        predicted = _normalize_level(row[f"predicted_{dim}"])
        matrix[expected][predicted] += 1
    return {exp: dict(preds) for exp, preds in sorted(matrix.items())}


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


def _score(rows: list[dict[str, Any]], dim: str) -> dict[str, Any]:
    n = len(rows)
    high = [r for r in rows if _normalize_level(r[f"expected_{dim}"]) == "high"]
    unknown = [r for r in rows if _normalize_level(r[f"expected_{dim}"]) == "unknown"]
    fp_den = [
        r for r in rows if _normalize_level(r[f"expected_{dim}"]) in {"low", "unknown"}
    ]
    fn_den = high
    return {
        "accuracy": sum(
            1
            for r in rows
            if _level_correct(r[f"expected_{dim}"], r[f"predicted_{dim}"])
        )
        / max(1, n),
        "high_risk_recall": sum(
            1
            for r in high
            if _normalize_level(r[f"predicted_{dim}"]) in HIGH_EQUIVALENT
        )
        / max(1, len(high)),
        "unknown_handling_accuracy": sum(
            1
            for r in unknown
            if _normalize_level(r[f"predicted_{dim}"]) in UNKNOWN_CORRECT
        )
        / max(1, len(unknown)),
        "false_positive_rate": sum(
            1 for r in fp_den if _normalize_level(r[f"predicted_{dim}"]) == "high"
        )
        / max(1, len(fp_den)),
        "false_negative_rate": sum(
            1
            for r in fn_den
            if _normalize_level(r[f"predicted_{dim}"]) in {"low", "unknown"}
        )
        / max(1, len(fn_den)),
        "confusion_matrix": _confusion_matrix(rows, dim),
    }


def evaluate_risk(path="data/eval/risk_eval.jsonl", use_reranker=False):
    try:
        from src.agents.evidence_agent import EvidenceAgent
        from src.agents.query_router_agent import QueryRouter
        from src.agents.risk_judge_agent import RiskJudgeAgent
    except Exception as e:
        return {
            "mode": "with_reranker" if use_reranker else "no_reranker",
            "per_sample": [],
            "metrics": {"overall_risk_accuracy": 0.0},
            "warning": f"evaluation dependencies unavailable: {e}",
        }
    samples = _load(path)
    q = QueryRouter()
    e = EvidenceAgent()
    j = RiskJudgeAgent()
    rows = []
    for s in samples:
        li = _listing_from_sample(s)
        ev = e.collect(
            li,
            q.route(f"{li.title} {li.description}").get("intents", []),
            enable_patent_check=bool(s.get("enable_patent_check", False)),
            enable_litigation_check=bool(s.get("enable_litigation_check", False)),
            use_reranker=use_reranker,
        )
        pred = j.judge(ev)
        got = pred.get("dimension_risks", {})

        row: dict[str, Any] = {
            "id": s["id"],
            "title": s.get("title", ""),
            "question": s.get("question", s.get("title", "")),
        }
        for dim, expected_key in RISK_FIELDS:
            row[f"expected_{dim}"] = _normalize_level(s.get(expected_key, "unknown"))
            row[f"predicted_{dim}"] = _normalize_level(got.get(dim, "unknown"))
        row["expected_overall_risk"] = _normalize_level(
            s.get("expected_overall_risk", "unknown")
        )
        row["predicted_overall_risk"] = _normalize_level(
            pred.get("overall_risk", "unknown")
        )
        row["correct"] = all(
            _level_correct(row[f"expected_{dim}"], row[f"predicted_{dim}"])
            for dim, _ in RISK_FIELDS
        ) and _level_correct(
            row["expected_overall_risk"], row["predicted_overall_risk"]
        )
        rows.append(row)

    metrics: dict[str, Any] = {}
    for dim, _ in RISK_FIELDS:
        dim_scores = _score(rows, dim)
        for name, value in dim_scores.items():
            metrics[f"{dim}_{name}"] = value
    metrics["overall_risk_accuracy"] = sum(
        1
        for r in rows
        if _level_correct(r["expected_overall_risk"], r["predicted_overall_risk"])
    ) / max(1, len(rows))
    metrics["overall_risk_confusion_matrix"] = _confusion_matrix(rows, "overall_risk")
    metrics["sample_accuracy"] = sum(1 for r in rows if r["correct"]) / max(
        1, len(rows)
    )
    return {
        "mode": "with_reranker" if use_reranker else "no_reranker",
        "per_sample": rows,
        "metrics": metrics,
    }
