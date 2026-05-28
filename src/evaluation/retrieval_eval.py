from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.retrieval.claim_retriever import ClaimRetriever
from src.retrieval.litigation_retriever import LitigationRetriever
from src.retrieval.platform_retriever import PlatformPolicyRetriever
from src.retrieval.trademark_retriever import TrademarkRetriever
from src.schemas import ListingInput


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _contains_keywords(texts: list[str], keywords: list[str]) -> bool:
    if not keywords:
        return True
    all_text = "\n".join(texts).lower()
    return any(k.lower() in all_text for k in keywords)


def evaluate_retrieval(path: str = "data/eval/retrieval_eval.jsonl") -> dict[str, Any]:
    samples = _load_jsonl(path)
    tm = TrademarkRetriever()
    lr = LitigationRetriever()
    results: list[dict[str, Any]] = []

    metric_hits = {
        "trademark_hit_rate": [],
        "platform_policy_recall_at_k": [],
        "claim_retrieval_recall_at_k": [],
        "litigation_patent_hit_rate": [],
    }

    for row in samples:
        q = row.get("query") or f"{row.get('title','')} {row.get('description','')}".strip()
        top_k = int(row.get("top_k", 5) or 5)
        expected_type = str(row.get("expected_source_type", "")).strip().lower()
        keywords = [str(x) for x in row.get("expected_keywords", [])]

        hit_tm = hit_platform = hit_claim = hit_lit = False
        detail: dict[str, Any] = {}

        try:
            listing = ListingInput(
                title=str(row.get("title") or row.get("query") or ""),
                description=str(row.get("description", "")),
                category=str(row.get("category", "")),
                platform=str(row.get("platform", "Temu")),
                has_authorization=bool(row.get("has_authorization", False)),
            )
            from src.listing.listing_parser import parse_listing

            parsed = parse_listing(listing)
            tm_matches = tm.search_trademarks(parsed)
            hit_tm = len(tm_matches) > 0 and _contains_keywords([m.mark_id_char for m in tm_matches], keywords)
            detail["trademark_matches"] = len(tm_matches)
        except Exception as e:  # noqa: BLE001
            detail["trademark_error"] = str(e)

        try:
            pp = PlatformPolicyRetriever(top_k=top_k).hybrid_search(q)
            hit_platform = len(pp) > 0 and _contains_keywords([x.snippet for x in pp], keywords)
            detail["platform_hits"] = len(pp)
        except Exception as e:  # noqa: BLE001
            detail["platform_error"] = str(e)

        try:
            cr = ClaimRetriever().hybrid_search(q, top_k=top_k)
            hit_claim = len(cr) > 0 and _contains_keywords([str(x.get("text", "")) for x in cr], keywords)
            detail["claim_hits"] = len(cr)
        except Exception as e:  # noqa: BLE001
            detail["claim_error"] = str(e)

        try:
            patent_ids = [str(x) for x in row.get("patent_ids", [])]
            if not patent_ids:
                patent_ids = [str(x.get("patent_id", "")) for x in row.get("expected_patents", []) if x]
            lit_found = 0
            for pid in patent_ids:
                if lr.get_litigation_summary(pid):
                    lit_found += 1
            hit_lit = lit_found > 0 if patent_ids else False
            detail["litigation_hits"] = lit_found
        except Exception as e:  # noqa: BLE001
            detail["litigation_error"] = str(e)

        metric_hits["trademark_hit_rate"].append(hit_tm)
        metric_hits["platform_policy_recall_at_k"].append(hit_platform)
        metric_hits["claim_retrieval_recall_at_k"].append(hit_claim)
        metric_hits["litigation_patent_hit_rate"].append(hit_lit)

        exp_map = {
            "trademark": hit_tm,
            "platform_policy": hit_platform,
            "patent_claim": hit_claim,
            "litigation": hit_lit,
        }
        overall_hit = exp_map.get(expected_type, any([hit_tm, hit_platform, hit_claim, hit_lit]))

        results.append({"id": row.get("id", ""), "query": q, "hit": overall_hit, "expected_source_type": expected_type, **detail})

    def _rate(vals: list[bool]) -> float:
        return 0.0 if not vals else sum(1 for x in vals if x) / len(vals)

    metrics = {k: _rate(v) for k, v in metric_hits.items()}
    metrics["total_samples"] = len(samples)
    metrics["overall_hit_rate"] = _rate([x["hit"] for x in results])

    return {"samples": results, "metrics": metrics}
